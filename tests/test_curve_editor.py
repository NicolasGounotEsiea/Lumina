"""Tests for lumina_control.curve_editor — monotone_lut, build_icc_bytes, compose_ramp."""
import struct

import pytest

from lumina_control.curve_editor import monotone_lut, build_icc_bytes, compose_ramp


# ── monotone_lut ─────────────────────────────────────────────────────────────

class TestMonotoneLut:
    def test_returns_256_entries(self):
        lut = monotone_lut([])
        assert len(lut) == 256

    def test_empty_points_returns_identity(self):
        lut = monotone_lut([])
        # First entry: 0, last: 65535
        assert lut[0] == 0
        assert lut[255] == 65535

    def test_identity_line(self):
        lut = monotone_lut([(0, 0), (1, 1)])
        assert lut[0] == 0
        assert lut[255] == 65535
        # Roughly linear in the middle
        assert abs(lut[127] - 65535 // 2) < 1000

    def test_all_entries_in_range(self):
        lut = monotone_lut([(0.2, 0.3), (0.8, 0.9)])
        assert all(0 <= v <= 65535 for v in lut)

    def test_monotone_output(self):
        lut = monotone_lut([(0.1, 0.0), (0.5, 0.7), (0.9, 1.0)])
        for i in range(len(lut) - 1):
            assert lut[i + 1] >= lut[i], f"Not monotone at index {i}"

    def test_flat_line(self):
        lut = monotone_lut([(0.0, 0.5), (1.0, 0.5)])
        # All entries should be ~32767
        mid = 65535 // 2
        assert all(abs(v - mid) <= 1 for v in lut)

    def test_single_control_point(self):
        lut = monotone_lut([(0.5, 0.5)])
        assert len(lut) == 256

    def test_out_of_range_points_clamped(self):
        lut = monotone_lut([(-0.5, 1.5), (0.5, 0.5)])
        assert all(0 <= v <= 65535 for v in lut)

    def test_duplicate_x_handled(self):
        lut = monotone_lut([(0.5, 0.3), (0.5, 0.7)])
        assert len(lut) == 256

    def test_endpoints_enforced_when_missing(self):
        lut = monotone_lut([(0.5, 0.8)])
        assert len(lut) == 256

    def test_s_curve_shape(self):
        lut = monotone_lut([(0, 0), (0.3, 0.1), (0.7, 0.9), (1, 1)])
        # First quarter should be darker than identity, last quarter brighter
        identity_at_64 = int(round(64 / 255 * 65535))
        identity_at_192 = int(round(192 / 255 * 65535))
        assert lut[64] < identity_at_64
        assert lut[192] > identity_at_192

    def test_out_max_parameter(self):
        lut = monotone_lut([], out_max=255)
        assert lut[255] == 255

    def test_all_entries_are_ints(self):
        lut = monotone_lut([(0, 0), (1, 1)])
        assert all(isinstance(v, int) for v in lut)


# ── build_icc_bytes ───────────────────────────────────────────────────────────

class TestBuildIccBytes:
    @pytest.fixture
    def identity_luts(self):
        lut = [int(round(i / 255 * 65535)) for i in range(256)]
        return lut, lut, lut

    def test_returns_bytes(self, identity_luts):
        r, g, b = identity_luts
        result = build_icc_bytes(r, g, b)
        assert isinstance(result, bytes)

    def test_header_is_128_bytes(self, identity_luts):
        r, g, b = identity_luts
        result = build_icc_bytes(r, g, b)
        # First 4 bytes = total size (big-endian uint32)
        total = struct.unpack(">I", result[:4])[0]
        assert total == len(result)

    def test_profile_size_matches_content(self, identity_luts):
        r, g, b = identity_luts
        data = build_icc_bytes(r, g, b)
        declared = struct.unpack(">I", data[:4])[0]
        assert declared == len(data)

    def test_icc_version_2(self, identity_luts):
        r, g, b = identity_luts
        data = build_icc_bytes(r, g, b)
        # Offset 8: version bytes
        assert data[8] == 0x02
        assert data[9] == 0x10

    def test_profile_class_is_mntr(self, identity_luts):
        r, g, b = identity_luts
        data = build_icc_bytes(r, g, b)
        assert data[12:16] == b"mntr"

    def test_colorspace_is_rgb(self, identity_luts):
        r, g, b = identity_luts
        data = build_icc_bytes(r, g, b)
        assert data[16:20] == b"RGB "

    def test_pcs_is_xyz(self, identity_luts):
        r, g, b = identity_luts
        data = build_icc_bytes(r, g, b)
        assert data[20:24] == b"XYZ "

    def test_file_signature_is_acsp(self, identity_luts):
        r, g, b = identity_luts
        data = build_icc_bytes(r, g, b)
        assert data[36:40] == b"acsp"

    def test_contains_desc_tag(self, identity_luts):
        r, g, b = identity_luts
        data = build_icc_bytes(r, g, b)
        assert b"desc" in data

    def test_contains_rtrc_tag(self, identity_luts):
        r, g, b = identity_luts
        data = build_icc_bytes(r, g, b)
        assert b"rTRC" in data

    def test_contains_creator_signature(self, identity_luts):
        r, g, b = identity_luts
        data = build_icc_bytes(r, g, b)
        # Profile creator: "LMNA"
        assert b"LMNA" in data

    def test_different_luts_produce_different_output(self):
        identity = [int(round(i / 255 * 65535)) for i in range(256)]
        boosted  = [min(65535, int(round(i / 255 * 65535 * 1.2))) for i in range(256)]
        data1 = build_icc_bytes(identity, identity, identity)
        data2 = build_icc_bytes(boosted, identity, identity)
        assert data1 != data2

    def test_minimum_viable_size(self, identity_luts):
        r, g, b = identity_luts
        data = build_icc_bytes(r, g, b)
        # Header(128) + tag_table(4+9*12=112) + tag data — should be several KB
        assert len(data) > 500


# ── compose_ramp ──────────────────────────────────────────────────────────────

class TestComposeRamp:
    @pytest.fixture
    def identity_lut(self):
        return [int(round(i / 255 * 65535)) for i in range(256)]

    def test_identity_params_return_identity(self, identity_lut):
        r, g, b = compose_ramp(identity_lut, identity_lut, identity_lut,
                               gamma=1.0, warmth=0.0, contrast=0.5,
                               r_gain=1.0, g_gain=1.0, b_gain=1.0)
        # Each output should be ~equal to input
        for i in range(256):
            assert abs(r[i] - identity_lut[i]) <= 2
            assert abs(g[i] - identity_lut[i]) <= 2
            assert abs(b[i] - identity_lut[i]) <= 2

    def test_returns_three_lists_of_256(self, identity_lut):
        r, g, b = compose_ramp(identity_lut, identity_lut, identity_lut)
        assert len(r) == len(g) == len(b) == 256

    def test_all_values_in_range(self, identity_lut):
        r, g, b = compose_ramp(identity_lut, identity_lut, identity_lut,
                               gamma=1.5, warmth=0.5, contrast=0.7)
        for lst in (r, g, b):
            assert all(0 <= v <= 65535 for v in lst)

    def test_warmth_reduces_blue(self, identity_lut):
        r, g, b = compose_ramp(identity_lut, identity_lut, identity_lut,
                               warmth=1.0)
        identity_at_128 = identity_lut[128]
        assert b[128] < identity_at_128

    def test_warmth_boosts_red(self, identity_lut):
        r, g, b = compose_ramp(identity_lut, identity_lut, identity_lut,
                               warmth=1.0)
        assert r[128] >= identity_lut[128]

    def test_higher_gamma_brightens_midtones(self, identity_lut):
        r_bright, _, _ = compose_ramp(identity_lut, identity_lut, identity_lut, gamma=2.0)
        r_normal, _, _ = compose_ramp(identity_lut, identity_lut, identity_lut, gamma=1.0)
        # Midtone at index 128
        assert r_bright[128] > r_normal[128]

    def test_zero_gain_blacks_out_channel(self, identity_lut):
        r, g, b = compose_ramp(identity_lut, identity_lut, identity_lut,
                               r_gain=0.0)
        # Red should be all zeros
        assert all(v == 0 for v in r)

    def test_contrast_above_half_increases_range(self, identity_lut):
        r_hi, _, _ = compose_ramp(identity_lut, identity_lut, identity_lut, contrast=0.8)
        r_id, _, _ = compose_ramp(identity_lut, identity_lut, identity_lut, contrast=0.5)
        # Midtone should remain similar, but range should increase
        assert r_hi[25] < r_id[25]    # darker shadows
        assert r_hi[230] > r_id[230]  # brighter highlights

    def test_contrast_below_half_reduces_range(self, identity_lut):
        r_lo, _, _ = compose_ramp(identity_lut, identity_lut, identity_lut, contrast=0.2)
        r_id, _, _ = compose_ramp(identity_lut, identity_lut, identity_lut, contrast=0.5)
        # Shadows brightened, highlights darkened
        assert r_lo[25] > r_id[25]
        assert r_lo[230] < r_id[230]

    def test_gamma_clamped_to_valid_range(self, identity_lut):
        # gamma < 0.5 → clamped to 0.5; should not raise
        r, g, b = compose_ramp(identity_lut, identity_lut, identity_lut, gamma=0.1)
        assert len(r) == 256

    def test_warmth_clamped(self, identity_lut):
        r, g, b = compose_ramp(identity_lut, identity_lut, identity_lut, warmth=5.0)
        assert all(0 <= v <= 65535 for v in b)
