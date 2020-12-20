import xlrd
import csv

county = "Franklin"
wb=xlrd.open_workbook("/Users/derekwillis/code/openelections-data-ky/detail.xls")

offices = {'U.S. House': "2", "State Representative 56": "3", 'State Representative 57': '4'}

results = []

# handle ballots cast
ballots = wb.sheet_by_name('Registered Voters')

for row_idx in range(1, ballots.nrows-1):
    precinct = ballots.cell(row_idx, 0).value
    ballots_cast = ballots.cell(row_idx, 2).value
    results.append([county, precinct, 'Ballots Cast', None, None, None, ballots_cast])

# handle offices
for office in [o for o in offices.keys()]:
    sheet = wb.sheet_by_name(offices[office])
    candidates = [x.value for x in sheet.row(1) if x.value != '']
    if len(candidates) == 5:
        parties = ['REP', 'DEM', 'LIB', 'IND', 'IND']
        cols = [3, 5, 7, 9, 11]
    else:
        parties = ['REP', 'DEM']
        cols = [3, 5]
    for row_idx in range(3, sheet.nrows-1):
        precinct = sheet.cell(row_idx, 0).value
        for candidate in candidates:
            idx = candidates.index(candidate)
            party = parties[idx]
            col = cols[idx]
            votes = sheet.cell(row_idx, col).value
            results.append([county, precinct, office, None, party, candidate, votes])

with open("20181106__ky__general__franklin_precinct.csv", "wt") as csvfile:
    w = csv.writer(csvfile)
    w.writerow(['county', 'office', 'district', 'party', 'candidate', 'votes'])
    w.writerows(results)
