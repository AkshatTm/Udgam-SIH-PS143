#!/usr/bin/env python3
"""
Stage 3 test suite. Owner: Jaiveer.

    python pipeline/attribute/tests.py          # all of it, a few seconds
    python pipeline/attribute/tests.py -v       # name every test as it runs

WHY THIS EXISTS
Stage 3's bugs do not crash. They produce a number that looks reasonable and names
the wrong ship. The COG sentinel is the worked example: AIS writes 360.0 to mean
"heading unknown", it affects 9.9% of rows in the Galveston extract, and left alone
every one of those rows claims a vessel was steaming due north. That is 15% of the
score, silently wrong, with nothing raising. It was caught by reading the data by
hand — this file is that audit made permanent.

Stage 2 has 20 known-answer assertions that caught a real 10x unit error before a
single particle moved. This is the same idea for Stage 3, and it goes in BEFORE the
scorer rather than after, because the scorer is the thing it has to catch.

NO NEW DEPENDENCIES. `unittest` is stdlib; pytest is not in requirements.txt and
nothing new goes in this close to the freeze (Master Part 5, rule 8).

Every fixture below is synthetic and hand-computed — the expected values are worked
out on paper, never read back out of the code being tested. A test that asserts what
the code currently does is not a test.

Scoring tests (haversine, grid sampling with row 0 = NORTH, the seven components and
their applicability gating) join this file as Phase 1 lands. Keep them here; one
command should run everything.
"""
import json
import math
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import geo                                     # noqa: E402
import ingest                                  # noqa: E402
from tracks import MAX_INTERP_GAP_MIN, Track, load_tracks   # noqa: E402

UTC = timezone.utc

NOAA_HEADER = ("MMSI,BaseDateTime,LAT,LON,SOG,COG,Heading,VesselName,IMO,CallSign,"
               "VesselType,Status,Length,Width,Draft,Cargo,TransceiverClass")


def row(mmsi, ts, lat, lon, sog=8.0, cog=90.0, heading=90.0,
        name="TEST VESSEL", vtype=70, cargo=""):
    """One NOAA-format CSV line. `ts` is 'YYYY-MM-DDTHH:MM:SS'."""
    return (f"{mmsi},{ts},{lat},{lon},{sog},{cog},{heading},{name},,,"
            f"{vtype},0,100,20,5.0,{cargo},A")


def write_csv(path, rows, header=NOAA_HEADER):
    Path(path).write_text(header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return str(path)


def dt(s):
    return datetime.fromisoformat(s).replace(tzinfo=UTC)


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="naap-stage3-"))

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def ingest_rows(self, rows, bbox=(-96.0, 28.0, -94.0, 30.0), window=None,
                    keep_cargo=False, name="AIS_2023_01_25.csv"):
        """Run the real ingest over synthetic rows, return the Parquet path."""
        csv = write_csv(self.dir / name, rows)
        out = self.dir / "out.parquet"
        ingest.ingest([csv], bbox, window, out, keep_cargo)
        return out

    def read_parquet(self, path, cols="mmsi", order="ts"):
        """Never select the raw `ts` column: DuckDB's Python conversion of TIMESTAMPTZ
        imports pytz, which is not in requirements.txt. Ask for epoch(ts) instead —
        the same reason load_tracks() does (tracks.py)."""
        import duckdb
        con = duckdb.connect()
        con.execute("SET TimeZone='UTC'")
        rows = con.execute(
            f"SELECT {cols} FROM read_parquet('{Path(path).as_posix()}') ORDER BY {order}"
        ).fetchall()
        con.close()
        return rows


# --------------------------------------------------------------------------- guard

class TestDayContinuityGuard(TempDirCase):
    """Risk D6. Merging non-consecutive days makes lag(ts) report the whole hole as a
    transponder silence for every vessel, so `gap` fires on the entire fleet — as a
    plausible signal, not as an error."""

    def _day(self, date_str, filename=None):
        return write_csv(self.dir / (filename or f"AIS_{date_str.replace('-', '_')}.csv"),
                         [row("367000001", f"{date_str}T00:01:54", 29.7, -95.1)])

    def test_single_day_passes(self):
        ingest.check_consecutive_days([self._day("2023-01-25")])

    def test_incident_plus_minus_two_days_passes(self):
        """A five-day span is the prescribed download and must NOT be refused.
        The rule is consecutive, not narrow."""
        days = [self._day(f"2023-01-{d}") for d in ("23", "24", "25", "26", "27")]
        ingest.check_consecutive_days(days)

    def test_order_does_not_matter(self):
        a, b, c = (self._day("2023-01-25"), self._day("2023-01-26"), self._day("2023-01-27"))
        ingest.check_consecutive_days([c, a, b])

    def test_three_week_hole_is_refused(self):
        """The exact merge that would have happened: 25 Jan + 16 Feb."""
        days = [self._day("2023-01-25"), self._day("2023-02-16")]
        with self.assertRaises(SystemExit) as e:
            ingest.check_consecutive_days(days)
        self.assertIn("not consecutive", str(e.exception))

    def test_one_missing_day_in_the_middle_is_refused(self):
        days = [self._day("2023-01-25"), self._day("2023-01-26"), self._day("2023-01-29")]
        with self.assertRaises(SystemExit) as e:
            ingest.check_consecutive_days(days)
        self.assertIn("not consecutive", str(e.exception))

    def test_same_day_twice_is_refused(self):
        days = [self._day("2023-01-25"), self._day("2023-01-25", "copy_of_the_25th.csv")]
        with self.assertRaises(SystemExit) as e:
            ingest.check_consecutive_days(days)
        self.assertIn("both cover", str(e.exception))

    def test_filename_disagreeing_with_contents_is_refused(self):
        """A renamed or wrongly-downloaded file. Filename says the 28th, data says the 25th."""
        bad = self._day("2023-01-25", "AIS_2023_01_28.csv")
        with self.assertRaises(SystemExit) as e:
            ingest.check_consecutive_days([bad])
        self.assertIn("named for", str(e.exception))

    def test_date_is_read_from_the_data_not_the_filename(self):
        self.assertEqual(ingest.first_row_date(self._day("2023-06-07", "no_date_here.csv")),
                         datetime(2023, 6, 7).date())


# -------------------------------------------------------------------------- sentinels

class TestSentinels(TempDirCase):
    """AIS encodes 'not available' as an in-range value, not a blank. Every one of
    these must become NULL, or it silently becomes a measurement."""

    def test_sog_102_3_becomes_null(self):
        p = self.ingest_rows([row("1", "2023-01-25T00:00:00", 29.0, -95.0, sog=102.3),
                              row("1", "2023-01-25T00:01:00", 29.0, -95.0, sog=8.4)])
        self.assertEqual([r[0] for r in self.read_parquet(p, "sog")], [None, 8.4])

    def test_cog_360_becomes_null(self):
        """The 9.9% bug. 360.0 means 'unknown', not 'due north' — and trajectory is
        15% of the score."""
        p = self.ingest_rows([row("1", "2023-01-25T00:00:00", 29.0, -95.0, cog=360.0),
                              row("1", "2023-01-25T00:01:00", 29.0, -95.0, cog=0.0)])
        self.assertEqual([r[0] for r in self.read_parquet(p, "cog")], [None, 0.0])

    def test_heading_511_becomes_null(self):
        p = self.ingest_rows([row("1", "2023-01-25T00:00:00", 29.0, -95.0, heading=511),
                              row("1", "2023-01-25T00:01:00", 29.0, -95.0, heading=270)])
        self.assertEqual([r[0] for r in self.read_parquet(p, "heading")], [None, 270.0])

    def test_real_values_just_below_the_sentinels_survive(self):
        """The boundary is where an over-eager filter eats real data. 359.9 is a real
        course; 101.9 knots is absurd but it is not the sentinel, so it stays."""
        p = self.ingest_rows([row("1", "2023-01-25T00:00:00", 29.0, -95.0,
                                  sog=101.9, cog=359.9, heading=510)])
        self.assertEqual(self.read_parquet(p, "sog, cog, heading"), [(101.9, 359.9, 510.0)])


# ----------------------------------------------------------------------------- filter

class TestFilter(TempDirCase):

    def test_bbox_keeps_inside_drops_outside(self):
        p = self.ingest_rows([
            row("inside", "2023-01-25T00:00:00", 29.0, -95.0),
            row("north", "2023-01-25T00:00:00", 31.0, -95.0),
            row("south", "2023-01-25T00:00:00", 27.0, -95.0),
            row("west", "2023-01-25T00:00:00", 29.0, -97.0),
            row("east", "2023-01-25T00:00:00", 29.0, -93.0),
        ], bbox=(-96.0, 28.0, -94.0, 30.0))
        self.assertEqual([r[0] for r in self.read_parquet(p, "mmsi")], ["inside"])

    def test_time_window_is_half_open(self):
        """[start, end) — a report exactly on `end` belongs to the next window."""
        w = (dt("2023-01-25T01:00:00"), dt("2023-01-25T02:00:00"))
        p = self.ingest_rows([
            row("a", "2023-01-25T00:59:59", 29.0, -95.0),
            row("b", "2023-01-25T01:00:00", 29.0, -95.0),
            row("c", "2023-01-25T01:30:00", 29.0, -95.0),
            row("d", "2023-01-25T02:00:00", 29.0, -95.0),
        ], window=w)
        self.assertEqual([r[0] for r in self.read_parquet(p, "mmsi")], ["b", "c"])

    def test_duplicate_mmsi_timestamp_is_dropped(self):
        """Two messages landing in the same second would put a zero-length interval in
        a track, which divides by zero when speed is derived from it."""
        p = self.ingest_rows([
            row("1", "2023-01-25T00:00:00", 29.0, -95.0, sog=8.0),
            row("1", "2023-01-25T00:00:00", 29.0, -95.0, sog=8.0),
            row("1", "2023-01-25T00:01:00", 29.1, -95.0, sog=8.5),
        ])
        self.assertEqual(self.read_parquet(p, "mmsi, epoch(ts), sog"),
                         [("1", 1674604800.0, 8.0), ("1", 1674604860.0, 8.5)])

    def test_bad_bbox_is_refused(self):
        csv = write_csv(self.dir / "AIS_2023_01_25.csv",
                        [row("1", "2023-01-25T00:00:00", 29.0, -95.0)])
        with self.assertRaises(SystemExit):
            ingest.ingest([csv], (-94.0, 28.0, -96.0, 30.0), None,
                          self.dir / "x.parquet", False)   # west > east


# ------------------------------------------------------------------------ vessel type

class TestVesselType(TempDirCase):
    """type_prior scores off this mapping, so its boundaries are score boundaries."""

    def test_mapping_and_its_boundaries(self):
        cases = [(30, "fishing"), (60, "passenger"), (69, "passenger"),
                 (70, "cargo"), (79, "cargo"), (80, "tanker"), (89, "tanker"),
                 (90, "other"), (31, "other"), (52, "other"), (29, "other")]
        rows = [row(str(code), "2023-01-25T00:00:00", 29.0, -95.0, vtype=code)
                for code, _ in cases]
        p = self.ingest_rows(rows)
        got = dict(self.read_parquet(p, "mmsi, vessel_type", order="mmsi"))
        for code, expected in cases:
            self.assertEqual(got[str(code)], expected, f"AIS type {code}")

    def test_tug_and_tow_land_in_other_not_a_category_of_their_own(self):
        """41.6% of the Galveston fleet. Documented so the day someone adds a `tug`
        label, this test fails and the change is deliberate rather than accidental."""
        p = self.ingest_rows([row("t", "2023-01-25T00:00:00", 29.0, -95.0, vtype=31)])
        self.assertEqual(self.read_parquet(p, "vessel_type"), [("other",)])

    def test_missing_vessel_type_becomes_other_not_a_crash(self):
        p = self.ingest_rows([row("1", "2023-01-25T00:00:00", 29.0, -95.0, vtype="")])
        self.assertEqual(self.read_parquet(p, "vessel_type, type_code"), [("other", None)])

    def test_mmsi_stays_a_string_and_keeps_its_leading_zero(self):
        """MMSI is an identifier, not a quantity. Through an int it loses the zero and
        stops matching vessels.geojson, which the validator checks."""
        p = self.ingest_rows([row("012345678", "2023-01-25T00:00:00", 29.0, -95.0)])
        self.assertEqual(self.read_parquet(p, "mmsi"), [("012345678",)])

    def test_cargo_column_detection(self):
        with_cargo = write_csv(self.dir / "a.csv",
                               [row("1", "2023-01-25T00:00:00", 29.0, -95.0)])
        without = write_csv(self.dir / "b.csv",
                            [row("1", "2023-01-25T00:00:00", 29.0, -95.0, cargo="")[:-2] + "A"],
                            header=NOAA_HEADER.replace(",Cargo", ""))
        self.assertTrue(ingest.has_cargo_column(with_cargo))
        self.assertFalse(ingest.has_cargo_column(without))


# ---------------------------------------------------------------------- origin -> box

class TestBoxFromOrigin(TempDirCase):
    """The seam: the same command runs against the fake origin and the real one."""

    def make_origin(self, r90=10.0, abstain=False):
        p = self.dir / "origin.json"
        p.write_text(json.dumps({
            "bounds": {"west": -95.0, "south": 29.0, "east": -94.0, "north": 30.0},
            "shape": [2, 2], "values": [0.0, 0.5, 0.5, 1.0],
            "centroid": [-94.5, 29.5], "radius_50_km": 4.0, "radius_90_km": r90,
            "time_window": ["2023-01-25T06:00:00Z", "2023-01-25T18:00:00Z"],
            "ensemble_runs": 50, "abstain": abstain}))
        return p

    def test_box_is_padded_to_two_times_r90(self):
        """2 x r90 is the `plausible` cut in the funnel, so nothing that could ever be
        called plausible is filtered away at read time."""
        bbox, window, abstain = ingest.box_from_origin(self.make_origin(r90=10.0), pad_hours=0)
        lat_pad = 20.0 / ingest.KM_PER_DEG            # 2 x 10 km, hand-computed
        self.assertAlmostEqual(bbox[1], 29.0 - lat_pad, places=6)
        self.assertAlmostEqual(bbox[3], 30.0 + lat_pad, places=6)
        self.assertGreater(bbox[2] - bbox[0], 1.0 + 2 * lat_pad,
                           "longitude pad must be wider than the latitude pad away "
                           "from the equator")
        self.assertFalse(abstain)

    def test_time_window_is_padded_both_sides(self):
        _, window, _ = ingest.box_from_origin(self.make_origin(), pad_hours=6)
        self.assertEqual(window[0], dt("2023-01-25T00:00:00"))
        self.assertEqual(window[1], dt("2023-01-26T00:00:00"))

    def test_abstain_flag_is_carried_through(self):
        self.assertTrue(ingest.box_from_origin(self.make_origin(abstain=True), 6)[2])

    def test_naive_timestamp_in_an_origin_is_rejected(self):
        p = self.make_origin()
        o = json.loads(p.read_text())
        o["time_window"] = ["2023-01-25T06:00:00", "2023-01-25T18:00:00Z"]   # no Z
        p.write_text(json.dumps(o))
        with self.assertRaises(SystemExit):
            ingest.box_from_origin(p, 6)


# ----------------------------------------------------------------------------- tracks

def make_track(offsets_minutes, mmsi="1", lon0=-95.0, lat0=29.0, step=0.01, sog=None):
    """A Track with reports at the given minute offsets, moving east at `step` deg."""
    t0 = dt("2023-01-25T00:00:00")
    ts = [t0 + timedelta(minutes=m) for m in offsets_minutes]
    n = len(ts)
    return Track(mmsi, "SYNTH", "cargo", 70, ts,
                 [lon0 + i * step for i in range(n)], [lat0] * n,
                 sog if sog is not None else [8.0] * n, [90.0] * n)


class TestTrackGeometry(unittest.TestCase):

    def test_max_gap_is_the_largest_silence(self):
        self.assertEqual(make_track([0, 5, 50, 55]).max_gap_minutes, 45.0)

    def test_gap_overlapping_counts_only_gaps_inside_the_window(self):
        """A vessel that went dark yesterday is not evidence about today."""
        t = make_track([0, 5, 50, 55])                       # the 45-min gap is 05:00-50:00
        self.assertEqual(t.gap_overlapping(dt("2023-01-25T00:20:00"),
                                           dt("2023-01-25T00:30:00")), 45.0)
        self.assertEqual(t.gap_overlapping(dt("2023-01-25T01:00:00"),
                                           dt("2023-01-25T02:00:00")), 0.0)

    def test_gap_touching_the_window_edge_does_not_count(self):
        t = make_track([0, 45])                              # gap spans 00:00 .. 00:45
        self.assertEqual(t.gap_overlapping(dt("2023-01-25T00:45:00"),
                                           dt("2023-01-25T01:00:00")), 0.0)

    def test_position_at_interpolates_the_midpoint(self):
        t = make_track([0, 10])                              # -95.00 -> -94.99
        lon, lat = t.position_at(dt("2023-01-25T00:05:00"))
        self.assertAlmostEqual(lon, -94.995, places=9)
        self.assertAlmostEqual(lat, 29.0, places=9)

    def test_the_interpolation_ceiling_is_thirty_minutes(self):
        """Pinned as a literal on purpose. 30 min is ~25x a normal reporting interval,
        so it fires only on genuine silences — that reasoning is what we defend, and
        moving the number should have to break a test rather than slip through."""
        self.assertEqual(MAX_INTERP_GAP_MIN, 30)

    def test_position_at_refuses_to_invent_a_position_across_a_long_gap(self):
        """The rule the whole stage rests on. An invented position can score as a
        suspect, and then we are accusing a ship of being somewhere we drew it.

        The fixture uses literal minutes, never MAX_INTERP_GAP_MIN — a test that
        builds itself from the constant it is checking moves when the constant moves
        and catches nothing. (Found by mutation testing: raising the ceiling to
        100000 left the earlier version of this test passing.)"""
        self.assertIsNone(make_track([0, 31]).position_at(dt("2023-01-25T00:15:00")))
        self.assertIsNone(make_track([0, 180]).position_at(dt("2023-01-25T01:00:00")))
        self.assertIsNone(make_track([0, 996]).position_at(dt("2023-01-25T08:00:00")))

    def test_position_at_allows_interpolation_right_up_to_the_ceiling(self):
        self.assertIsNotNone(make_track([0, 30]).position_at(dt("2023-01-25T00:15:00")))
        self.assertIsNotNone(make_track([0, 29]).position_at(dt("2023-01-25T00:15:00")))

    def test_position_at_is_none_outside_the_track(self):
        t = make_track([10, 20])
        self.assertIsNone(t.position_at(dt("2023-01-25T00:00:00")))
        self.assertIsNone(t.position_at(dt("2023-01-25T01:00:00")))

    def test_position_at_returns_the_exact_report_when_it_lands_on_one(self):
        t = make_track([0, 10, 20])
        self.assertEqual(t.position_at(dt("2023-01-25T00:10:00")), (-94.99, 29.0))

    def test_median_sog_ignores_nulls(self):
        t = make_track([0, 1, 2, 3], sog=[None, 2.0, 4.0, 6.0])
        self.assertEqual(t.median_sog(), 4.0)

    def test_median_sog_is_none_when_every_report_is_null(self):
        self.assertIsNone(make_track([0, 1], sog=[None, None]).median_sog())


class TestTrackOutput(unittest.TestCase):

    def test_decimation_caps_points_and_keeps_both_endpoints(self):
        t = make_track(list(range(1200)))
        coords = t.coordinates(max_points=500)
        self.assertLessEqual(len(coords), 500)
        self.assertEqual(coords[0], [round(t.lon[0], 5), round(t.lat[0], 5)])
        self.assertEqual(coords[-1], [round(t.lon[-1], 5), round(t.lat[-1], 5)])

    def test_short_track_is_not_decimated(self):
        t = make_track(list(range(9)))
        self.assertEqual(len(t.coordinates(max_points=500)), 9)

    def test_feature_reports_the_undecimated_count(self):
        """Contract 6.6: n_points is the real number of reports, not the rendered one.
        Reporting the decimated count would understate the evidence behind a track."""
        t = make_track(list(range(1200)))
        f = t.to_feature()
        self.assertEqual(f["properties"]["n_points"], 1200)
        self.assertLessEqual(len(f["geometry"]["coordinates"]), 500)

    def test_feature_matches_the_contract_shape(self):
        f = make_track([0, 1, 2]).to_feature()
        self.assertEqual(f["type"], "Feature")
        self.assertEqual(f["geometry"]["type"], "LineString")
        for key in ("mmsi", "name", "vessel_type", "n_points", "max_gap_minutes"):
            self.assertIn(key, f["properties"])

    def test_coordinates_are_lon_lat_and_rounded_to_five_places(self):
        """Frozen convention 1. A swap here is invisible until the map draws Antarctica."""
        t = make_track([0], lon0=-95.123456789, lat0=29.987654321)
        self.assertEqual(t.coordinates(), [[-95.12346, 29.98765]])


class TestTrackLoading(TempDirCase):

    def test_tracks_under_five_points_are_dropped(self):
        rows = ([row("keeper", f"2023-01-25T00:0{i}:00", 29.0, -95.0) for i in range(5)] +
                [row("tooshort", f"2023-01-25T00:0{i}:00", 29.0, -95.0) for i in range(4)])
        tracks = load_tracks(self.ingest_rows(rows))
        self.assertEqual(sorted(tracks), ["keeper"])
        self.assertEqual(len(tracks["keeper"]), 5)

    def test_reports_come_back_in_time_order_however_the_file_is_ordered(self):
        rows = [row("1", f"2023-01-25T00:{m:02d}:00", 29.0, -95.0)
                for m in (40, 10, 50, 20, 30)]
        t = load_tracks(self.ingest_rows(rows))["1"]
        self.assertEqual(t.ts, sorted(t.ts))
        self.assertEqual(t.max_gap_minutes, 10.0)

    def test_timestamps_come_back_timezone_aware_utc(self):
        rows = [row("1", f"2023-01-25T00:0{i}:00", 29.0, -95.0) for i in range(5)]
        t = load_tracks(self.ingest_rows(rows))["1"]
        self.assertIsNotNone(t.ts[0].tzinfo)
        self.assertEqual(t.ts[0].utcoffset(), timedelta(0))
        self.assertEqual(t.start, dt("2023-01-25T00:00:00"))


# --------------------------------------------------------------------------- geometry

class TestDistanceAndBearing(unittest.TestCase):
    """Every reported distance goes through haversine. Euclidean is fine at Galveston
    and wrong off Alaska, which is the worst kind of bug: right where you test it."""

    def test_one_degree_of_latitude_is_111_2_km_anywhere(self):
        for lat in (0.0, 29.35, 59.55):
            self.assertAlmostEqual(geo.haversine_km(0.0, lat, 0.0, lat + 1.0),
                                   111.195, delta=0.01, msg=f"at {lat} N")

    def test_a_degree_of_longitude_shrinks_with_latitude(self):
        at_equator = geo.haversine_km(0.0, 0.0, 1.0, 0.0)
        at_sixty = geo.haversine_km(0.0, 60.0, 1.0, 60.0)
        self.assertAlmostEqual(at_equator, 111.195, delta=0.01)
        self.assertAlmostEqual(at_sixty, at_equator * math.cos(math.radians(60.0)),
                               delta=0.2)

    def test_zero_distance_and_symmetry(self):
        self.assertEqual(geo.haversine_km(-94.7, 29.35, -94.7, 29.35), 0.0)
        self.assertAlmostEqual(geo.haversine_km(-94.7, 29.35, -94.0, 30.0),
                               geo.haversine_km(-94.0, 30.0, -94.7, 29.35), places=12)

    def test_euclidean_would_be_materially_wrong_at_alaskan_latitudes(self):
        """The reason A3 says use haversine. This is a claim about the *error*, so it
        stays true however haversine is implemented."""
        lon0, lat0, lat1 = -142.7, 59.55, 60.05        # the Alaska case's latitude
        true_km = geo.haversine_km(lon0, lat0, lon0 + 1.0, lat1)
        naive_km = math.hypot(1.0, lat1 - lat0) * geo.KM_PER_DEG_LAT
        self.assertGreater(abs(naive_km - true_km) / true_km, 0.40,
                           "flat-earth distance should be badly wrong at 60 N")

    def test_bearing_at_the_four_cardinals(self):
        for dlon, dlat, expected in ((0, 1, 0.0), (1, 0, 90.0), (0, -1, 180.0), (-1, 0, 270.0)):
            self.assertAlmostEqual(geo.bearing_deg(0.0, 0.0, dlon, dlat), expected, places=6)

    def test_bearing_is_always_in_zero_to_360(self):
        for lon, lat in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
            b = geo.bearing_deg(0.0, 0.0, lon, lat)
            self.assertGreaterEqual(b, 0.0)
            self.assertLess(b, 360.0)

    def test_angular_difference_wraps_around_north(self):
        """355 and 5 are ten degrees apart, not 350. Get this wrong and the trajectory
        component rejects everything heading nearly due north."""
        self.assertAlmostEqual(geo.angular_difference_deg(355.0, 5.0), 10.0, places=9)
        self.assertAlmostEqual(geo.angular_difference_deg(5.0, 355.0), 10.0, places=9)
        self.assertAlmostEqual(geo.angular_difference_deg(0.0, 180.0), 180.0, places=9)
        self.assertAlmostEqual(geo.angular_difference_deg(90.0, 90.0), 0.0, places=9)

    def test_point_to_segment(self):
        d, t = geo.point_to_segment_km(0.0, 0.0, 0.0, 0.0, 1.0, 0.0)
        self.assertAlmostEqual(d, 0.0, places=9)
        d, t = geo.point_to_segment_km(0.5, 0.0, 0.0, 0.0, 1.0, 0.0)   # on the segment
        self.assertAlmostEqual(d, 0.0, delta=1e-6)
        self.assertAlmostEqual(t, 0.5, places=6)
        d, t = geo.point_to_segment_km(2.0, 0.0, 0.0, 0.0, 1.0, 0.0)   # past the far end
        self.assertAlmostEqual(t, 1.0, places=6)
        self.assertAlmostEqual(d, geo.KM_PER_DEG_LAT, delta=0.5)

    def test_point_to_segment_handles_a_zero_length_segment(self):
        d, t = geo.point_to_segment_km(0.0, 1.0, 0.0, 0.0, 0.0, 0.0)
        self.assertAlmostEqual(d, 111.195, delta=0.01)


# ------------------------------------------------------------------------- grid sample

def grid_doc(values, rows=3, cols=3, west=-95.0, south=29.0, east=-94.0, north=30.0,
             abstain=False):
    return {"bounds": {"west": west, "south": south, "east": east, "north": north},
            "shape": [rows, cols], "values": values,
            "centroid": [(west + east) / 2, (south + north) / 2],
            "radius_50_km": 4.0, "radius_90_km": 12.0,
            "time_window": ["2023-01-25T06:00:00Z", "2023-01-25T18:00:00Z"],
            "ensemble_runs": 50, "abstain": abstain}


class TestOriginGrid(unittest.TestCase):

    def test_row_zero_is_north(self):
        """The one that matters most. An upside-down grid validates cleanly, scores
        cleanly, and points at the wrong water — Anushka's test 5d exists for exactly
        this, and so does this one (frozen convention 5).

        Grid is all zeros except the top-left cell, which is the NORTH-WEST corner.
        """
        g = geo.OriginGrid(grid_doc([1.0, 0.0, 0.0,
                                     0.0, 0.0, 0.0,
                                     0.0, 0.0, 0.0]))
        self.assertEqual(g.sample(-95.0, 30.0), 1.0, "north-west corner should be the hot cell")
        self.assertEqual(g.sample(-95.0, 29.0), 0.0, "south-west corner must be cold")
        self.assertEqual(g.sample(-94.0, 30.0), 0.0, "north-east corner must be cold")
        self.assertEqual(g.sample(-94.0, 29.0), 0.0, "south-east corner must be cold")

    def test_rowcol_maps_the_corners(self):
        g = geo.OriginGrid(grid_doc([0.0] * 9))
        self.assertEqual(g.rowcol(-95.0, 30.0), (0.0, 0.0))       # NW -> row 0, col 0
        self.assertEqual(g.rowcol(-94.0, 29.0), (2.0, 2.0))       # SE -> last row, last col
        self.assertEqual(g.rowcol(-94.5, 29.5), (1.0, 1.0))       # centre

    def test_sample_outside_the_grid_is_a_measured_zero(self):
        """Zero, not None. A vessel that never entered the reconstructed origin has a
        proximity of zero, and that is a real statement about it. Not-applicable is a
        different thing."""
        g = geo.OriginGrid(grid_doc([1.0] * 9))
        self.assertEqual(g.sample(-100.0, 29.5), 0.0)
        self.assertEqual(g.sample(-94.5, 40.0), 0.0)
        self.assertFalse(g.contains(-100.0, 29.5))
        self.assertTrue(g.contains(-94.5, 29.5))

    def test_sample_returns_the_value_of_the_nearest_cell(self):
        g = geo.OriginGrid(grid_doc([0.0, 0.0, 0.0,
                                     0.0, 0.7, 0.0,
                                     0.0, 0.0, 0.0]))
        self.assertEqual(g.sample(-94.5, 29.5), 0.7)
        self.assertEqual(g.sample(-94.52, 29.52), 0.7, "still nearest the centre cell")
        self.assertEqual(g.sample(-95.0, 29.5), 0.0)

    def test_peak_is_found_at_the_right_corner(self):
        g = geo.OriginGrid(grid_doc([0.0, 0.0, 0.0,
                                     0.0, 0.0, 0.0,
                                     0.0, 0.0, 1.0]))
        lon, lat = g.peak_lonlat()                                # south-east cell
        self.assertAlmostEqual(lon, -94.0, places=9)
        self.assertAlmostEqual(lat, 29.0, places=9)

    def test_shape_disagreeing_with_values_is_refused(self):
        with self.assertRaises(SystemExit) as e:
            geo.OriginGrid(grid_doc([0.0] * 8))
        self.assertIn("implies", str(e.exception))

    def test_inverted_bounds_are_refused(self):
        with self.assertRaises(SystemExit):
            geo.OriginGrid(grid_doc([0.0] * 9, west=-94.0, east=-95.0))

    def test_abstain_and_radii_are_carried(self):
        g = geo.OriginGrid(grid_doc([0.0] * 9, abstain=True))
        self.assertTrue(g.abstain)
        self.assertEqual((g.radius_50_km, g.radius_90_km), (4.0, 12.0))


class TestGridOnTheRealFixture(unittest.TestCase):
    """Against the committed Galveston fixture, so the file and the reader are checked
    together rather than only against a hand-made dict."""

    FIXTURE = HERE / "fixtures" / "case-gulf-fake" / "origin.json"

    def setUp(self):
        if not self.FIXTURE.exists():
            self.skipTest("fixture not generated — run make_fake_case.py")
        self.g = geo.OriginGrid.load(self.FIXTURE)

    def test_grid_peaks_at_one_and_the_peak_sits_at_the_centroid(self):
        self.assertAlmostEqual(max(self.g.values), 1.0, places=6)
        plon, plat = self.g.peak_lonlat()
        self.assertLess(geo.haversine_km(plon, plat, *self.g.centroid), 2.0)

    def test_the_cloud_is_a_streak_not_a_circle(self):
        """The fixture exists to exercise D8. If someone regenerates it circular, grid
        sampling and circle membership stop disagreeing and the test loses its point."""
        clon, clat = self.g.centroid

        def half_width_km(dlon, dlat):
            """How far the >0.5 contour reaches from the centroid along one direction."""
            reach = 0.0
            for i in range(1, 400):
                lon, lat = clon + dlon * 0.005 * i, clat + dlat * 0.005 * i
                if self.g.sample(lon, lat) > 0.5:
                    reach = geo.haversine_km(clon, clat, lon, lat)
            return reach

        along = max(half_width_km(0, 1), half_width_km(0, -1))
        across = max(half_width_km(1, 0), half_width_km(-1, 0))
        self.assertGreater(along / max(across, 1e-9), 2.0,
                           f"fixture cloud should be clearly elongated, got "
                           f"{along:.1f} km along vs {across:.1f} km across")


if __name__ == "__main__":
    unittest.main(verbosity=2 if "-v" in sys.argv else 1)
