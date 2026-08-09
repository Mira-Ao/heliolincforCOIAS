#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import math
import re
from datetime import date


def parse_date_arg(value):
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid date '{value}'. Use YYYY-MM-DD."
        )


def parse_ra(value):
    parts = re.split(r"[\s:]+", value.strip())
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(
            f"Invalid RA '{value}'. Use 'hh mm ss'."
        )
    try:
        h, m, s = map(float, parts)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid RA '{value}'. Use 'hh mm ss'."
        )
    if not (0 <= h < 24 and 0 <= m < 60 and 0 <= s < 60):
        raise argparse.ArgumentTypeError(f"Invalid RA '{value}'.")
    return 15.0 * (h + m / 60.0 + s / 3600.0)


def parse_dec(value):
    text = value.strip()
    parts = re.split(r"[\s:]+", text)
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(
            f"Invalid Dec '{value}'. Use 'dd mm ss', e.g. '-12 05 00'."
        )
    try:
        d_raw, m, s = map(float, parts)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid Dec '{value}'.")
    sign = -1.0 if d_raw < 0 or text.startswith("-") else 1.0
    d = abs(d_raw)
    if not (0 <= d <= 90 and 0 <= m < 60 and 0 <= s < 60):
        raise argparse.ArgumentTypeError(f"Invalid Dec '{value}'.")
    if d == 90 and (m != 0 or s != 0):
        raise argparse.ArgumentTypeError(f"Invalid Dec '{value}'.")
    return sign * (d + m / 60.0 + s / 3600.0)


def parse_mpc80(line):
    if len(line) < 80:
        return None
    try:
        year = int(line[15:19])
        month = int(line[20:22])
        day_value = float(line[23:32])
        obs_date = date(year, month, int(day_value))

        hour = int(line[32:34])
        minute = int(line[35:37])
        second = float(line[38:44])
        if not (0 <= hour < 24 and 0 <= minute < 60 and 0 <= second < 60):
            return None
        ra_deg = 15.0 * (hour + minute / 60.0 + second / 3600.0)

        sign = line[44]
        if sign not in ("+", "-"):
            return None
        deg = int(line[45:47])
        dec_min = int(line[48:50])
        dec_sec = float(line[51:56])
        if not (0 <= deg <= 90 and 0 <= dec_min < 60 and 0 <= dec_sec < 60):
            return None
        if deg == 90 and (dec_min != 0 or dec_sec != 0):
            return None
        dec_deg = deg + dec_min / 60.0 + dec_sec / 3600.0
        if sign == "-":
            dec_deg *= -1.0

        obscode = line[77:80].strip()
        return obs_date, ra_deg, dec_deg, obscode
    except (ValueError, IndexError, OverflowError):
        return None


def angular_distance_deg(ra1, dec1, ra2, dec2):
    ra1, dec1, ra2, dec2 = map(
        math.radians, (ra1, dec1, ra2, dec2)
    )
    cos_angle = (
        math.sin(dec1) * math.sin(dec2)
        + math.cos(dec1) * math.cos(dec2) * math.cos(ra1 - ra2)
    )
    cos_angle = max(-1.0, min(1.0, cos_angle))
    return math.degrees(math.acos(cos_angle))


def main():
    parser = argparse.ArgumentParser(
        description="Search an MPC 80-column ITF with optional filters."
    )
    parser.add_argument("--itf", required=True, help="Input MPC80 ITF file")
    parser.add_argument("--output", required=True, help="Output ITF file")
    parser.add_argument("--startdate", type=parse_date_arg,
                        help="Start date, inclusive: YYYY-MM-DD")
    parser.add_argument("--enddate", type=parse_date_arg,
                        help="End date, inclusive: YYYY-MM-DD")
    parser.add_argument("--RA", dest="ra", type=parse_ra,
                        help="Central RA: 'hh mm ss'")
    parser.add_argument("--Dec", dest="dec", type=parse_dec,
                        help="Central Dec: 'dd mm ss' or '-dd mm ss'")
    parser.add_argument("--deg", type=float,
                        help="Radius in degrees")
    parser.add_argument("--station",
                        help="MPC observatory code, e.g. T09")
    args = parser.parse_args()

    if args.startdate and args.enddate and args.startdate > args.enddate:
        parser.error("--startdate must not be later than --enddate.")

    if (args.ra is None) != (args.dec is None):
        parser.error("--RA and --Dec must be specified together.")

    if args.deg is not None:
        if args.ra is None or args.dec is None:
            parser.error("--deg requires both --RA and --Dec.")
        if not 0 <= args.deg <= 180:
            parser.error("--deg must be between 0 and 180.")

    station = args.station.strip() if args.station else None

    total = valid = ignored = output_count = 0

    print("Reading:", args.itf)

    with open(args.itf, "r", encoding="utf-8-sig",
              errors="replace", newline="") as infile, \
         open(args.output, "w", encoding="utf-8", newline="\n") as outfile:

        for raw in infile:
            total += 1
            line = raw.rstrip("\r\n")
            parsed = parse_mpc80(line)

            if parsed is None:
                ignored += 1
                continue

            valid += 1
            obs_date, ra_deg, dec_deg, obscode = parsed

            if args.startdate and obs_date < args.startdate:
                continue
            if args.enddate and obs_date > args.enddate:
                continue
            if station is not None and obscode != station:
                continue

            if args.ra is not None:
                if angular_distance_deg(
                    args.ra, args.dec, ra_deg, dec_deg
                ) > args.deg:
                    continue

            outfile.write(line + "\n")
            output_count += 1

    print("Done.")
    print(f"Total input lines     : {total}")
    print(f"Valid MPC80 lines     : {valid}")
    print(f"Ignored invalid lines : {ignored}")
    print(f"Output observations   : {output_count}")
    print(f"Output file           : {args.output}")


if __name__ == "__main__":
    main()
