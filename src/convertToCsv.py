#!/usr/bin/env python3

import csv
import os.path
import re
import sys
import xml.etree.ElementTree as ET

class Table:
    def __init__(self):
        self.filename = None
        self.worksheetName = None
        self.data = []

    def shouldProcess(self):
        return len(self.data) > 0 and len(self.data[0]) > 0 \
               and self.data[0][0] is not None \
               and self.data[0][0] != 'Precinct'

    def getCounty(self):
        county = os.path.splitext(os.path.basename(self.filename))[0]
        if county.endswith(' county') or county.endswith(' County'):
            return county[:-7]
        else:
            return county

    def getOffice(self):
        office = self.data[0][0]
        office = re.sub(r' \(Vote for \d+\)', '', office, flags=re.IGNORECASE)
        district = ''
        match = re.search(r',? ([0-9][A-Za-z0-9 ]+) District', office)
        if match is not None:
            office = office.replace(match.group(0), '')
            district = match.group(1).split(' ')[0]
            if district[0].isdigit():
                district = district[:-2]
        return (office, district)

    def getResults(self):
        results = {}
        # find the candidates
        candidateIndexes = {}
        for index in range(0, len(self.data[1])):
            if self.data[1][index] is not None:
                candidateIndexes[self.data[1][index]] = index
        # process the data
        for row in self.data[3:]:
            precinct = row[0]
            if precinct[0:5] == 'Total' or precinct[0:5] == 'total':
                continue
            for candidateName, candidateIndex in candidateIndexes.items():
                if candidateName not in results:
                    results[candidateName] = {}
                results[candidateName][precinct] = int(row[candidateIndex + 1])
        return results


def readTables(filenames):
    '''Reads a bunch of XML Excel spreadsheets and returns the tables found
    in the files.'''
    namespace = '{urn:schemas-microsoft-com:office:spreadsheet}'
    tables = []
    for filename in filenames:
        tree = ET.parse(filename)
        root = tree.getroot()
        sheetId = 0
        for worksheetEle in root.findall(namespace + 'Worksheet'):
            sheetId = sheetId + 1
            tableId = 0
            for tableEle in worksheetEle.findall(namespace + 'Table'):
                table = Table()
                table.filename = filename
                table.worksheetName = worksheetEle.get(namespace + 'Name')
                if table.worksheetName is None:
                    table.worksheetName = 'Sheet ' + str(sheetId)
                for rowEle in tableEle.findall(namespace + 'Row'):
                    columns = []
                    for cellEle in rowEle.findall(namespace + 'Cell'):
                        dataEle = cellEle.find(namespace + 'Data')
                        if dataEle.attrib[namespace + 'Type'] == 'Number':
                            columns.append(float(dataEle.text))
                        else:
                            columns.append(dataEle.text)
                        mergeAcross = cellEle.get(namespace + 'MergeAcross')
                        if mergeAcross is not None:
                            for i in range(0, int(mergeAcross)):
                                columns.append(None)
                    table.data.append(columns)
                tables.append(table)
    return tables

###############################################################################
if __name__ == '__main__':
    if len(sys.argv) <= 1:
        print('usage: convertToCsv.py <xmlFile> ...')
        sys.exit(1)
    # construct the CSV
    csvHeader = ['county', 'precinct', 'office', 'district', 'party', 'candidate', 'votes']
    csvData = []
    for table in readTables(sys.argv[1:]):
        if table.shouldProcess():
            county = table.getCounty()
            office, district = table.getOffice()
            votesByCandidateByPrecinct = table.getResults()
            precincts = None
            for candidate in sorted(votesByCandidateByPrecinct.keys()):
                if precincts is None:
                    precincts = sorted(votesByCandidateByPrecinct[candidate].keys())
                for precinct in precincts:
                    row = {
                        'county': county,
                        'precinct': precinct,
                        'office': office,
                        'district': district,
                        'candidate': candidate,
                        'votes': votesByCandidateByPrecinct[candidate][precinct]
                    }
                    csvData.append(row)
    # write the CSV
    with open('output.csv', 'w') as csvfile:
        csvWriter = csv.DictWriter(csvfile, fieldnames=csvHeader)
        csvWriter.writeheader()
        csvWriter.writerows(csvData)
