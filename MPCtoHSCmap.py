#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import csv
import sys


def parse_mpc80(line):
    """
    Parse one MPC 80-column observation.

    Returns:
        [ID, date, RA, Dec, mag, band, code]

    Returns None if the line does not conform to the
    required MPC80 fields.
    """

    if len(line) < 80:
        return None

    try:
        # ---------------------------------------------------------
        # Object ID
        # MPC columns 1-12
        # Keep '*' because it can indicate the first observation
        # of a tracklet.
        # ---------------------------------------------------------
        object_id = line[0:12].strip()

        if not object_id:
            return None

        # ---------------------------------------------------------
        # Date
        # MPC columns 16-32
        # Example:
        # C2017 01 26.56962
        # ---------------------------------------------------------
        date_string = line[14:32].strip()

        # Basic validation of the date field.
        # The expected form is:
        # CYYYY MM DD.ddddd
        if len(date_string) < 10:
            return None

        # ---------------------------------------------------------
        # RA
        # MPC columns 33-44
        # Example:
        # 09 53 18.35
        # ---------------------------------------------------------
        ra = line[32:44].strip()

        if len(ra) == 0:
            return None

        # Validate RA numerically.
        rah = int(line[32:34])
        ram = int(line[35:37])
        ras = float(line[38:44])

        if not (0 <= rah < 24):
            return None

        if not (0 <= ram < 60):
            return None

        if not (0 <= ras < 60):
            return None

        # ---------------------------------------------------------
        # Dec
        # MPC columns 45-56
        # Example:
        # +01 02 23.2
        # ---------------------------------------------------------
        dec = line[44:56].strip()

        if len(dec) == 0:
            return None

        dec_sign = line[44]

        if dec_sign not in ("+", "-"):
            return None

        decd = int(line[45:47])
        decm = int(line[48:50])
        decs = float(line[51:56])

        if not (0 <= decd <= 90):
            return None

        if not (0 <= decm < 60):
            return None

        if not (0 <= decs < 60):
            return None

        if decd == 90 and (decm != 0 or decs != 0):
            return None

        # ---------------------------------------------------------
        # Magnitude
        # MPC columns 66-70
        # ---------------------------------------------------------
        mag = line[65:70].strip()

        if mag:
            try:
                float(mag)
            except ValueError:
                return None
        else:
            # Keep blank magnitude as blank.
            mag = ""

        # ---------------------------------------------------------
        # Band
        # MPC column 71
        # ---------------------------------------------------------
        band = line[70].strip()

        # ---------------------------------------------------------
        # Observatory code
        # MPC columns 78-80
        # ---------------------------------------------------------
        code = line[77:80].strip()

        if not code:
            return None

        return [
            object_id,
            date_string,
            ra,
            dec,
            mag,
            band,
            code
        ]

    except (ValueError, IndexError, OverflowError):
        return None


def main():

    parser = argparse.ArgumentParser(
        description=(
            "Convert MPC 80-column observations to "
            "#ID,date,RA,Dec,mag,band,code CSV."
        )
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Input MPC80 file."
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Output CSV file."
    )

    args = parser.parse_args()

    total_lines = 0
    valid_lines = 0
    ignored_lines = 0

    print(f"Reading: {args.input}")

    with open(
        args.input,
        "r",
        encoding="utf-8-sig",
        errors="replace",
        newline=""
    ) as infile, open(
        args.output,
        "w",
        encoding="utf-8",
        newline=""
    ) as outfile:

        writer = csv.writer(
            outfile,
            lineterminator="\n"
        )

        # Header
        writer.writerow([
            "#ID",
            "date",
            "RA",
            "Dec",
            "mag",
            "band",
            "code"
        ])

        for raw_line in infile:

            total_lines += 1

            line = raw_line.rstrip("\r\n")

            result = parse_mpc80(line)

            if result is None:
                ignored_lines += 1
                continue

            writer.writerow(result)
            valid_lines += 1

    print("Done.")
    print(f"Total input lines : {total_lines}")
    print(f"Valid MPC80 lines : {valid_lines}")
    print(f"Ignored lines     : {ignored_lines}")
    print(f"Output CSV        : {args.output}")


if __name__ == "__main__":
    main()