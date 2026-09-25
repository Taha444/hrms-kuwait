# -*- coding: utf-8 -*-
"""SW-019 / M21 #6 — الأرقام الطويلة في CSV تُفتح نصًّا لا بصيغة علمية، دون فتح باب لحقن الصيغ."""
import csv
import io

from app.exports import to_csv


def _cells(rows):
    text = to_csv(["h"], rows).decode("utf-8").lstrip("\ufeff")
    return [r[0] for r in csv.reader(io.StringIO(text))][1:]


def test_long_digit_strings_are_written_as_text_for_excel():
    cells = _cells([["298012345678"], [298012345678], ["12345"], ["+96512345678"], ["=1+1"]])
    assert cells == ['="298012345678"', '="298012345678"', "12345", "+96512345678", "'=1+1"]
