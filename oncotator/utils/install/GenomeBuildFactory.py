from copy import deepcopy
import logging
from shove.core import Shove
from oncotator.Transcript import Transcript
from oncotator.index.gaf import region2bin
from oncotator.utils.MutUtils import MutUtils
from oncotator.utils.install.GenomeBuildInstallUtils import GenomeBuildInstallUtils
from BCBio import GFF
from Bio import SeqIO

class GenomeBuildFactory(object):
    """ Responsible for creating indices for genome builds (through ENSEMBL) and creating a set of datasource files.
        The methods in this class would typically be run in datasource creation, not during annotation.
    """

    QUALS_TO_CHECK = ['gene_status', 'level', 'source', 'tag', 'ccdsid', 'transcript_name', 'transcript_type', 'havana_gene', 'havana_transcript', 'transcript_status']

    def __init__(self):
        self._transcript_index = dict()

    def _convertGFFRecordToTranscript(self, gff_record, seq_dict, seq_dict_keys):
        """

        :param gff_record:
        :param seq_dict:
        :return: None if the record is a gene record or otherwise does not represent a transcript, CDS, *_codon, or exon
        """
        types_of_interest = ["exon", "CDS", "start_codon", "stop_codon"]
        if gff_record['type'] not in types_of_interest:
            return None

        quals = gff_record['quals']
        transcript_id = quals['transcript_id'][0]


        if transcript_id not in self._transcript_index.keys():
            contig = MutUtils.convertChromosomeStringToMutationDataFormat(gff_record['rec_id'])
            tx = Transcript(transcript_id, gene=quals['gene_name'][0], gene_id=quals['gene_id'][0], contig=contig)
            self._transcript_index[transcript_id] = tx

            # Set the gene_type based on gene_type or gene_biotype
            key = "gene_biotype"
            if key not in quals.keys():
                key = "gene_type"
            self._transcript_index[transcript_id].set_gene_type(quals[key][0])

            if gff_record['strand'] == 1:
                self._transcript_index[transcript_id].set_strand("+")
            else:
                self._transcript_index[transcript_id].set_strand("-")

            for attribute in GenomeBuildFactory.QUALS_TO_CHECK:
                if attribute in quals.keys():
                    self._transcript_index[transcript_id].add_other_attribute(attribute, quals[attribute])

            seq = seq_dict.get(transcript_id, None)

            if seq is None:
                # Try to parse the key.  Some fasta files embed the transcript id in with a lot of other info.
                for k in seq_dict_keys:
                    if k.find(transcript_id) != -1:
                        seq = seq_dict.get(k)
                        break

            if seq is not None:
                genome_seq_as_str = str(seq.seq)
            else:
                genome_seq_as_str = ""

            self._transcript_index[transcript_id].set_seq(genome_seq_as_str)

        if gff_record['type'] == 'exon':
            self._transcript_index[transcript_id].add_exon(gff_record['location'][0], gff_record['location'][1], quals['exon_number'][0])
        elif gff_record['type'] == 'CDS':
            self._transcript_index[transcript_id].add_cds(gff_record['location'][0], gff_record['location'][1])
        elif gff_record['type'] == 'start_codon':
            self._transcript_index[transcript_id].set_start_codon(gff_record['location'][0], gff_record['location'][1])
        elif gff_record['type'] == 'stop_codon':
            self._transcript_index[transcript_id].set_stop_codon(gff_record['location'][0], gff_record['location'][1])

    def build_ensembl_transcript_index(self, ensembl_input_gtf, ensembl_input_fasta, output_filename, protocol="file"):
        """Create the transcript index (using shove) for ensembl.  Key is transcript ID
        :param ensembl_input_gtf:
        :param ensembl_input_fasta: sequence data for transcripts corresponding to what is in the gtf
        :param output_filename:
        :param protocol: shove protocol.  Usually "file" or "sqlite"
        """

        # Example code taken from http://biopython.org/wiki/GFF_Parsing
        shove = Shove(protocol + "://" + output_filename, "memory://")
        logging.getLogger(__name__).info("Transcript index being created: " + protocol + "://" + output_filename)

        in_seq_file = ensembl_input_fasta
        in_seq_handle = open(in_seq_file)
        seq_dict = SeqIO.to_dict(SeqIO.parse(in_seq_handle, "fasta"))
        in_seq_handle.close()
        logging.getLogger(__name__).info("Parsed fasta file: " + in_seq_file)

        in_file = ensembl_input_gtf
        in_handle = open(in_file)
        seq_dict_keys = seq_dict.keys()
        ctr = 0
        for rec in GFF.parse_simple(in_file): #(in_handle, base_dict=seq_dict):

            # transcript id seems to always be a list of length 1
            if len(rec['quals']['transcript_id']) > 1:
                logging.getLogger(__name__).warn("ensembl records had more than one transcript id: " + str(rec['quals']['transcript_id']))

            self._convertGFFRecordToTranscript(rec, seq_dict, seq_dict_keys)
            ctr += 1
            if (ctr % 100 ) == 0:
                logging.getLogger(__name__).info("Added " + str(ctr) + " lines of the gtf into internal transcript index.")

        logging.getLogger(__name__).info("Populating final db with internal transcript index.")
        transcript_index_keys = self._transcript_index.keys()
        for k in transcript_index_keys:
            shove[k] = self._transcript_index[k]

        logging.getLogger(__name__).info("Transcript index created " + str(shove.keys()) + " transcripts.")
        shove.close()
        in_handle.close()

    def build_ensembl_transcripts_by_gene_index(self, ensembl_transcript_index_fname, output_filename, protocol="file"):
        """ Create an index for gene --> transcripts using a transcript index created in build_ensembl_transcript_index
        :param ensembl_transcript_index_fname: file/dir location for ensembl transcript db
        :return:
        """

        #TODO: This may need to be moved to the init of the transcript datasource as that may be faster.

        transcript_db = Shove(protocol + "://" + ensembl_transcript_index_fname, "memory://")
        output_db = Shove(protocol + "://" + output_filename, "memory://", optimize=False)

        transcript_keys = transcript_db.keys()

        for tx_id in transcript_keys:
            tx = transcript_db[tx_id]
            gene = tx.get_gene()
            if gene not in output_db.keys():
                output_db[gene] = [tx]
            else:
                # This must be done like this, since we have to store the new value in the db.
                tmpList = output_db[gene]
                tmpList.append(tx)
                output_db[gene] = tmpList

        output_db.close()
        transcript_db.close()

    def build_ensembl_transcripts_by_genomic_location_index(self, ensembl_transcript_index_fname, output_filename, protocol="file"):
        """Create an index for genomic position to transcripts index, using a transcript index created in
            build_ensembl_transcript_index
        """
        transcript_db = Shove(protocol + "://" + ensembl_transcript_index_fname)
        output_db = Shove(protocol + "://" + output_filename, optimize=False)

        transcript_keys = transcript_db.keys()

        for tx_id in transcript_keys:
            tx = transcript_db[tx_id]
            start = tx.get_start()
            end = tx.get_end()
            genomic_location_bin = region2bin(start, end)
            key = tx.get_contig() + "_" + str(genomic_location_bin)
            if key not in output_db:
                output_db[key] = [tx]
            else:
                tmpList = output_db[key]
                tmpList.append(tx)
                output_db[key] = tmpList

        output_db.close()
        transcript_db.close()

    # def build_ensembl_protein_seqs(self):
    #     prot_seq_db = shelve.open(os.path.join(output_dir, 'Ensembl_protein_seqs.fa.shlv'), 'c')
    #     for prot_rec in SeqIO.parse(proteins_file, 'fasta'):
    #         tmp = re.search('ENST\d+', prot_rec.description)
    #         if tmp == None:
    #             continue
    #         id_str = tmp.group(0)
    #         prot_seq_db[id_str] = str(prot_rec.seq)
    #
    #     prot_seq_db.close()

    def construct_ensembl_indices(self, ensembl_input_gtf, ensembl_input_fasta, base_output_filename):
        """

        :param ensembl_input_gtf: gtf input file
        :param ensembl_input_fasta: fasta input file
        :param base_output_filename: Just the base output filename, such as "my_ensembl" without any extensions.
        :return:
        """
        ensembl_transcript_index_filename = base_output_filename + ".transcript.idx"
        self.build_ensembl_transcript_index(ensembl_input_gtf, ensembl_input_fasta, ensembl_transcript_index_filename)
        self.build_ensembl_transcripts_by_gene_index(ensembl_transcript_index_filename, base_output_filename + ".transcript_by_gene.idx")
        self.build_ensembl_transcripts_by_genomic_location_index(ensembl_transcript_index_filename, base_output_filename + ".transcript_by_gp_bin.idx")
