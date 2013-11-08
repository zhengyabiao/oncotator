import math


class TranscriptProviderUtils(object):

    @staticmethod
    def infer_variant_type(reference_allele, observed_allele):
        """ To go completely in annotate method.  Returns variant type string."""
        if reference_allele == '-': #is insertion
            return 'INS'
        elif observed_allele == '-': #is deletion
            return 'DEL'
        else:
            if len(observed_allele) != len(reference_allele):
                return 'ONP'
            elif len(reference_allele) == 1:
                return 'SNP'
            elif len(reference_allele) == 2:
                return 'DNP'
            elif len(reference_allele) == 3:
                return 'TNP'
            elif len(reference_allele) > 3:
                return 'ONP'

        raise Exception('Variant Type cannot be inferred from reference and observed allele: (%s, %s)' % (reference_allele, observed_allele))

    @staticmethod
    def retrieve_effect_dict():
        """Used for ordering the effect given the variant_classification"""
        return {
        'De_novo_Start_OutOfFrame':0,
        'Nonsense_Mutation':0,
        'Nonstop_Mutation':0,
        'Missense_Mutation':1,
        'De_novo_Start_InFrame':1,
        'In_Frame_Del':1,
        'In_Frame_Ins':1,
        'Frame_Shift_Del':2,
        'Frame_Shift_Ins':2,
        'Frame_Shift_Sub':2,
        'Start_Codon_SNP':3,
        'Start_Codon_Del':3,
        'Start_Codon_Ins':3,
        'Start_Codon_DNP':3,
        'Start_Codon_TNP':3,
        'Start_Codon_ONP':3,
        'Stop_Codon_SNP':3,
        'Stop_Codon_Del':3,
        'Stop_Codon_Ins':3,
        'Stop_Codon_DNP':3,
        'Stop_Codon_TNP':3,
        'Stop_Codon_ONP':3,
        'Splice_Site':4,
        'Splice_Site_SNP':4,
        'Splice_Site_Del':4,
        'Splice_Site_Ins':4,
        'Splice_Site_DNP':4,
        'Splice_Site_TNP':4,
        'Splice_Site_ONP':4,
        'Splice_Site':4,
        'miRNA':4,
        'Silent':5,
        "3'UTR":6,
        "5'UTR":6,
        'Intron':7,
        "5'Flank":8,
        "3'Flank":8,
        'Non-coding_Transcript':9,
        'IGR':20,
        'TX-REF-MISMATCH':100
        }

    @staticmethod
    def test_overlap(a_st, a_en, b_st, b_en):
        """Test if two genomic start, end tuples overlap.  """
        if (a_st >= b_st and a_st <= b_en) or (a_en >= b_st and a_en <= b_en) or \
            (a_st <= b_st and a_en >= b_en):
            return True
        else:
            return False

    @staticmethod
    def test_overlap_with_strand(a_st, a_en, b_st, b_en, strand):
        if strand == '+':
            if a_st <= b_st and a_en >= b_en: return 'a_encompasses_b'
            elif a_st >= b_st and a_en <= b_en: return 'a_within_b'
            elif a_st < b_st and a_en >= b_st: return 'a_overlaps_b_left_border'
            elif a_st <= b_en and a_en >= b_en: return 'a_overlaps_b_right_border'
            else: return None
        elif strand == '-':
            b_st, b_en = b_en, b_st
            if a_st <= b_st and a_en >= b_en: return 'a_encompasses_b'
            elif a_st >= b_st and a_en <= b_en: return 'a_within_b'
            elif a_st < b_st and a_en >= b_st: return 'a_overlaps_b_right_border'
            elif a_st <= b_en and a_en >= b_en: return 'a_overlaps_b_left_border'
            else: return None

    @staticmethod
    def _determine_genome_change(chr, start, end, ref_allele, alt_allele, variant_type):
        genome_change = ''
        start = int(start)
        end = int(end)
        if variant_type == 'SNP':
            genome_change = 'g.chr%s:%d%s>%s' % (chr, start, ref_allele,
                                                 alt_allele)
        elif variant_type.endswith('NP'):
            genome_change = 'g.chr%s:%d_%d%s>%s' % (chr, start, end,
                                                    ref_allele, alt_allele)
        elif variant_type == 'DEL':
            if start == end:
                genome_change = 'g.chr%s:%ddel%s' % (chr, start, ref_allele)
            else:
                genome_change = 'g.chr%s:%d_%ddel%s' % (chr, start, end, ref_allele)
        elif variant_type == 'INS':
            genome_change = 'g.chr%s:%d_%dins%s' % (chr, start, end,
                                                    alt_allele)
        return genome_change

    # TODO: These transforms should be in a separate class.
    @staticmethod
    def _transform_to_feature_space(exons, s, strand):
        """
        Assumes exons are in order given strand, though their start > end
        :param exons:
        :param s:
        :param strand:
        :return:
        """
        d = 0
        for exon in exons:
            if s >= exon[0] and s < exon[1]:
                if strand == "-":
                    d += (exon[1] - s)
                else:
                    d += (s - exon[0])
                break
            elif (s > exon[1] and strand == "+") or (s < exon[0] and strand == "-"):
                d += (exon[1] - exon[0])
            else:
                break
        return d

    @staticmethod
    def _convert_genomic_space_to_feature_space(s, e, features, strand):
        d_start = TranscriptProviderUtils._transform_to_feature_space(features, s, strand)
        d_end = TranscriptProviderUtils._transform_to_feature_space(features, e, strand)
        if strand == "-":
            tmp = d_start
            d_start = d_end
            d_end = tmp
        return d_start, d_end

    @staticmethod
    def convert_genomic_space_to_exon_space(start, end, tx):
        s = int(start)
        e = int(end)
        strand = tx.get_strand()
        exons = tx.get_exons()
        return TranscriptProviderUtils._convert_genomic_space_to_feature_space(s, e, exons, strand)

    @staticmethod
    def convert_genomic_space_to_cds_space(start, end, tx):
        s = int(start)
        e = int(end)
        strand = tx.get_strand()
        cds = tx.get_cds()
        return TranscriptProviderUtils._convert_genomic_space_to_feature_space(s, e, cds, strand)

    @staticmethod
    def convert_genomic_space_to_transcript_space(start, end, tx):
        """ start <= end, regardless of strand for this method
        This includes all exons, UTR, but not padding.

        :param start: str position in genome space  start <= end
        :param end: str position in genome space    start <= end
        :return (list of str and length 2) ["-1", "-1"] if position cannot be mapped.  Note that here start cannot be greater or less than
            end (start, end).  The strand of transcript is taken into account.
        """
        s = int(start)
        e = int(end)

        tx_start = int(tx.determine_transcript_start())
        tx_end = int(tx.determine_transcript_stop())

        result = ["-1", "-1"]

        if tx.get_strand() == "-":
            if e <= tx_start:
                result[0] = tx_start - e
            if s >= tx_end:
                result[1] = tx_start - s
        else:
            if e <= tx_end:
                result[1] = e - tx_start
            if s >= tx_start:
                result[0] = s - tx_start
        return result[0], result[1]

    @staticmethod
    def get_protein_positions(transcript_position_start, transcript_position_end, cds_start):
        """Parameters are all in transcript space """
        protein_position_start = int(math.ceil((float(transcript_position_start) - float(cds_start) + 1) /3))
        if transcript_position_end == transcript_position_start:
            protein_position_end = protein_position_start
        else:
            protein_position_end = int(math.ceil((float(transcript_position_end) - float(cds_start) + 1) /3))
        return protein_position_start, protein_position_end

    @staticmethod
    def get_cds_codon_positions(protein_position_start, protein_position_end, cds_start):
        """cds_Start is in transcript space """
        cds_codon_start = (protein_position_start * 3 - 2) + cds_start - 1
        cds_codon_end = (protein_position_end * 3) + cds_start - 1
        return cds_codon_start, cds_codon_end
