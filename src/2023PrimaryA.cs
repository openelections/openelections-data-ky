using System.Globalization;
using CsvHelper;
using CsvHelper.Configuration;
using System.Text.RegularExpressions;

namespace General2023A;
// written in C# for .NET 8
// add Nuget Package CsvHelper
public class Program
{
    public static void Main(string[] args)
    {
        string savePath = "/Dev/OpenElections/Kentucky/Downloads/2023/Primary/Extracts/";
        List<string> counties = new List<string> 
        { 
            "Allen", "Ballard", "Barren", "Boone", "Bourbon", "Boyd"
        };
        List<PartyAssociation> partyAssociations = new List<PartyAssociation>
        {
            new PartyAssociation() { keyword = "BESHEAR", party = "DEM", name="Andy BESHEAR"},
            new PartyAssociation() { keyword = "Peppy", party = "DEM", name="Peppy MARTIN"},
            new PartyAssociation() { keyword = "YOUNG", party = "DEM", name="Geoffrey M. \"Geoff\" YOUNG"},
            new PartyAssociation() { keyword = "CAMERON", party = "REP", name="Daniel CAMERON"},
            new PartyAssociation() { keyword = "CRAFT", party = "REP", name="Kelly CRAFT"},
            new PartyAssociation() { keyword = "QUARLES", party = "REP", name="Ryan QUARLES"},
            new PartyAssociation() { keyword = "DETERS", party = "REP", name="Eric DETERS"},
            new PartyAssociation() { keyword = "HARMON", party = "REP", name="Mike HARMON"},
            new PartyAssociation() { keyword = "KECK", party = "REP", name="Alan KECK"},
            new PartyAssociation() { keyword = "O. COOPER", party = "REP", name="David O. COOPER"},
            new PartyAssociation() { keyword = "C. SMITH", party = "REP", name="Robbie C. SMITH"},
            new PartyAssociation() { keyword = "DeVORE", party = "REP", name="Bob DeVORE"},
            new PartyAssociation() { keyword = "RICE", party = "REP", name="Johnny Ray RICE"},
            new PartyAssociation() { keyword = "ORMEROD", party = "REP", name="Dennis Ray ORMEROD"},
            new PartyAssociation() { keyword = "CLARK", party = "REP", name="Jacob CLARK"},
            new PartyAssociation() { keyword = "ADAMS", party = "REP", name="Michael ADAMS"},
            new PartyAssociation() { keyword = "KNIPPER", party = "REP", name="Stephen L. KNIPPER"},
            new PartyAssociation() { keyword = "MARICLE", party = "REP", name="Allen MARICLE"},
            new PartyAssociation() { keyword = "BALL", party = "REP", name="Allison BALL"},
            new PartyAssociation() { keyword = "PETTEYS", party = "REP", name="Derek PETTEYS"},
            new PartyAssociation() { keyword = "METCALF", party = "REP", name="Mark H. METCALF"},
            new PartyAssociation() { keyword = "COOPERRIDER", party = "REP", name="Andrew COOPERRIDER"},
            new PartyAssociation() { keyword = "OLEKA", party = "REP", name="O. C. \"OJ\" OLEKA"},
            new PartyAssociation() { keyword = "ENLOW", party = "DEM", name="Sierra J. ENLOW"},
            new PartyAssociation() { keyword = "MALONE", party = "DEM", name="Mikael MALONE"},
            new PartyAssociation() { keyword = "SHELL", party = "REP", name="Jonathan SHELL"},
            new PartyAssociation() { keyword = "HEATH", party = "REP", name="Richard HEATH"}
        };

        List<FindOffice> findOffices = new List<FindOffice>
         {
            new FindOffice() { keyword = "county", office=""},
            new FindOffice() { keyword = "question", office=""},
            new FindOffice() { keyword = "COMMONWEALTH", office=""},
            new FindOffice() { keyword = "SURVEYOR", office=""},
            new FindOffice() { keyword = "CIRCUIT", office=""},
            new FindOffice() { keyword = "BOARD", office=""},
            new FindOffice() { keyword = "mayor", office=""},
            new FindOffice() { keyword = "CONSTABLE", office=""},
            new FindOffice() { keyword = "MAGISTRATE", office=""},
            new FindOffice() { keyword = "coroner", office=""},
            new FindOffice() { keyword = "judge", office=""},
            new FindOffice() { keyword = "justice of the peace", office=""},
            new FindOffice() { keyword = "sheriff", office=""},
            new FindOffice() { keyword = "jailer", office=""},
            new FindOffice() { keyword = "president", office="President"},
            new FindOffice() { keyword = "governor", office="Governor"},
            new FindOffice() { keyword = "general", office="Attorney General"},
            new FindOffice() { keyword = "secretary", office="Secretary of State"},
            new FindOffice() { keyword = "treasurer", office="State Treasurer"},
            new FindOffice() { keyword = "agriculture", office="Commissioner of Agriculture"},
            new FindOffice() { keyword = "auditor", office="Auditor of Public Accounts"}
         };

        List<string> skipWords = new List<string>
         {
            "choice"
         };

        foreach(string county in counties)
        {
            string csvPath = savePath + "tabula-"+county+"Primary.csv";
            string finalCsvPath = savePath + "DataFiles/20230516__ky__general__" + county.ToLower() + "__precinct.csv";
            List<CandidateVote> candidateVotes = new();
            string party="";
            if (File.Exists(csvPath))
            {
                string? precinct = string.Empty;
                string? district= string.Empty;
                string? office = string.Empty;
                string? wParty = string.Empty;
                var csvConfig=new CsvConfiguration(CultureInfo.CurrentCulture);
                csvConfig.HasHeaderRecord=false;
                using var streamReader =  File.OpenText(csvPath);
                using var csvReader = new CsvReader(streamReader,csvConfig);
                string? strvalue="";        
                while (csvReader.Read())
                {
                    CandidateVote candidateVote = new();
                    candidateVote.county=county;
                    candidateVote.precinct=precinct;
                    candidateVote.office=office;
                    csvReader.TryGetField<string?>(0,out strvalue);
                    
                    string? shftPointer = "";
                    string? intStr1= "";
                    string? intStr2= "";
                    string? intStr3= "";
                    string? intStr4= "";
                    string? intStr5= "";
                    string? intStr6= "";
                    string? intStr7= "";
                    string? intStr8= "";
                    string? intStr9= "";
                    string? intStr10= "";
                    string? intStr11= "";
                    string? intStr12= "";
                    string? intStr13= "";                   
                    

                    try
                    {
                        // if the string in the first column of the row contains on of the substrings in the skipWords list then skip to the next line
                        var doSkip = skipWords.First(item => strvalue.Contains(item, StringComparison.OrdinalIgnoreCase));
                        if (doSkip != null) continue;
                    
                    } catch (Exception) {}

                    // reset office if string in first column contains an office name
                    try
                    {
                        var findOffice = findOffices.First(item => strvalue.Contains(item.keyword, StringComparison.OrdinalIgnoreCase));
                        if (findOffice != null)
                        {
                            office = findOffice.office;
                            continue;
                        }
                        if (String.IsNullOrEmpty(office)) continue;
                    } catch (Exception) {} 

                    /*
                        Categorize the row based on which columns Tabitha has placed data
                                 Absentee  Early   ElectionDay  Total       lastfill
                        shft0A      1%       2%         3%        4           5%
                        shft0A      1        2          3         4           4
                        shft0A      1%       2%         3%        4%          4%
                        shft1A      2%       3%         4%        5%          5%
                        shft1A      2        3          4         5           5
                        shft1A      2%       3%         4%        5           6%
                        shft2A      0%       1%         2%        3           4%
                        shft2A      0        1          2         3           3
                        
                     */
                    try
                    {
                        csvReader.TryGetField<string?>(1, out intStr1);
                        csvReader.TryGetField<string?>(2, out intStr2);
                        csvReader.TryGetField<string?>(3, out intStr3);
                        csvReader.TryGetField<string?>(4, out intStr4);
                        csvReader.TryGetField<string?>(5, out intStr5);
                        csvReader.TryGetField<string?>(6, out intStr6);
                        csvReader.TryGetField<string?>(7, out intStr7);
                        csvReader.TryGetField<string?>(8, out intStr8);
                        csvReader.TryGetField<string?>(9, out intStr9);
                        csvReader.TryGetField<string?>(10, out intStr10);
                        csvReader.TryGetField<string?>(11, out intStr11);
                        csvReader.TryGetField<string?>(12, out intStr12);
                        csvReader.TryGetField<string?>(13, out intStr13);
                    } catch (Exception) {}

                    if (!string.IsNullOrEmpty(intStr6)) shftPointer="shft1A";
                    else if (!string.IsNullOrEmpty(intStr5) && !intStr5.Contains("allots"))
                    {
                        if (intStr5.Contains("%")) 
                        {
                            if (intStr4.Contains("%")) shftPointer="shft1A";
                            else shftPointer="shft0A";
                        }
                        else shftPointer = "shft1A";
                    }
                    else if (!string.IsNullOrEmpty(intStr4))
                    {
                        if (intStr3.Contains("%")) shftPointer="shft0A";
                        else if (intStr2.Contains("%")) shftPointer="shft2A";
                        else shftPointer="shft0A";
                    }
                    else if (!string.IsNullOrEmpty(intStr3)) shftPointer="shft2A";

                    
                   
                    string[] wdlst = strvalue.Split("-");
                    if (Regex.IsMatch(wdlst[0].Trim(), @"^[A-Z]{1}\d{3}$") || Regex.IsMatch(wdlst[0].Trim(), @"^[A-Z]{1}\d{3}[A-Z]{1}$") || Regex.IsMatch(wdlst[0].Trim(), @"^[A-Z]{1}\d{3}[A-Z]{2}$"))
                    {
                        if (wdlst.Length == 1) precinct = wdlst[0].Trim();
                        else precinct=(wdlst[0]+" "+wdlst[1]).Trim();
                        office=string.Empty;
                        continue;
                    }
                    

                    if (String.IsNullOrEmpty(strvalue) || String.IsNullOrWhiteSpace(strvalue))
                    {
                        if (intStr1.Contains("Undervotes") || intStr1.Contains("Overvotes") || intStr1.Contains("Cast Votes")) strvalue=intStr1;
                        else continue;
                    } 
                    if (String.IsNullOrEmpty(strvalue)) continue;
                    string[]? words = strvalue.Split(" ");
                    string wName= string.Empty;
                    int wrdCnt = 0;
                    bool loopMore = true;

                    Console.WriteLine(""+precinct+" "+strvalue+" "+shftPointer);

                    if (shftPointer == "shft0A")
                    {
                        candidateVote.candidate= strvalue;                        
                        candidateVote.absentee = GetInt(intStr1);
                        candidateVote.early_voting = GetInt(intStr2);
                        candidateVote.election_day = GetInt(intStr3);
                        candidateVote.votes = GetInt(intStr4);
                    }
                    else if (shftPointer == "shft1A")
                    {
                        candidateVote.candidate= strvalue;                        
                        candidateVote.absentee = GetInt(intStr2);
                        candidateVote.early_voting = GetInt(intStr3);
                        candidateVote.election_day = GetInt(intStr4);
                        candidateVote.votes = GetInt(intStr5);
                    }
                    else foreach(string? word in words)
                    {
                        if (word.Any(char.IsDigit) && loopMore)
                        {
                            try
                            {   
                                candidateVote.absentee = GetInt(word);
                                candidateVote.candidate= wName;
                                if (shftPointer == "shft2A")
                                {
                                    candidateVote.early_voting = GetInt(intStr1);
                                    candidateVote.election_day = GetInt(intStr2);
                                    candidateVote.votes = GetInt(intStr3);
                                    loopMore=false;
                                }
                            }
                            catch (Exception) {}
                        }
                        else
                        {
                            wName = wName + word + " ";                            
                        }
                        ++wrdCnt;
                    }
                    
                    try
                    {
                        var assoc = partyAssociations.First(item => candidateVote.candidate.Contains(item.keyword,StringComparison.OrdinalIgnoreCase));
                        if (assoc != null)
                        {
                            if (!candidateVote.candidate.Contains("Votes",StringComparison.OrdinalIgnoreCase) && !candidateVote.candidate.Contains("UNCOMMITTED",StringComparison.OrdinalIgnoreCase))
                            {
                                candidateVote.party= assoc.party;
                                party = assoc.party;
                            } 
                            candidateVote.district = assoc.district;
                            candidateVote.candidate = assoc.name;
                            district = assoc.district;
                        }
                    } catch (Exception) {}                  
                    if (candidateVote.candidate == null) continue;
                    if (candidateVote.candidate.Contains("Undervotes:"))
                     {
                        candidateVote.candidate = "Under Votes";
                        candidateVote.party = party;
                        candidateVote.district = district;
                     }
                    if (candidateVote.candidate.Contains("Overvotes:"))
                     {
                        candidateVote.candidate = "Over Votes";
                        candidateVote.party = party;
                        candidateVote.district = district;
                     }
                    if (candidateVote.candidate.Contains("Cast Votes"))
                    {
                        candidateVote.candidate = "Total Votes Cast";
                        candidateVote.party = party;
                        candidateVote.district = district;
                    }
                    if (candidateVote.candidate.Contains("UNCOMMITTED"))
                    {
                        candidateVote.candidate= "UNCOMMITTED";
                        candidateVote.party = party;
                        candidateVote.district = district;
                    }
                    if (String.IsNullOrEmpty(candidateVote.office))
                    {
                        continue;
                    }
                    candidateVote.candidate = candidateVote.candidate.Replace("REP","").Replace("DEM","").Trim();
                    candidateVotes.Add(candidateVote);                   
                    
                }

            }          
            
            using (var writerC=new StreamWriter(finalCsvPath))
            using (var csvC=new CsvWriter(writerC,CultureInfo.InvariantCulture))
            {
                csvC.Context.RegisterClassMap<CandidateVoteMap>();
                csvC.WriteRecords(candidateVotes);
                csvC.Flush();
            }
            Console.WriteLine(""+county);
        }
    }

    public static int GetInt(string numb)
    {
        string[] numbs = numb.Trim().Split(" ");
        return Convert.ToInt32(numbs[0].Replace(",","").Trim());
    }

    public class PartyAssociation
    {
        public string keyword { get; set; }
        public string party { get; set; }
        public string? district { get; set; } = null;
        public string? name { get; set; }
    }

    public class FindOffice
    {
        public string keyword { get; set;}
        public string? office { get; set; }
    }
    public class CandidateVote
    {
        public string? county { get; set; }
        public string? precinct { get; set; }
        public string? office { get; set; }
        public string? district { get; set; }
        public string? party { get; set; }
        public string? candidate { get; set; }
        public int? votes { get; set; }
        public int? early_voting { get; set; }
        public int? election_day { get; set; }
        public int? absentee { get; set; }

    }

    public sealed class CandidateVoteMap : ClassMap<CandidateVote>
    {
        public CandidateVoteMap()
        {
            Map(m => m.county);
            Map(m => m.precinct);
            Map(m => m.office);
            Map(m => m.district);
            Map(m => m.party);
            Map(m => m.candidate);
            Map(m => m.votes);
            Map(m => m.early_voting);
            Map(m => m.election_day);
            Map(m => m.absentee);
        }
    }


}

