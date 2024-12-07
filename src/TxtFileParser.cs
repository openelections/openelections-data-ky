using System.Globalization;
using CsvHelper;
using CsvHelper.Configuration;
using System.Text.RegularExpressions;

namespace TxtFileParser;
/*
 * .NET 8 Console Application written in C#
 * Requires addition of CsvHelper Nuget Package
 * Reads lines of text file, 
 * iterates through lines extracting county names and precinct turnout counts,
 * stores data in list of Output objects, and
 * writes List of Output objects to csv file (using CsvHelper)
*/
public class Program
{
    public static void Main(string[] args)
    {
        string filePath = "/Dev/OpenElections/Kentucky/Downloads/2012/";
        string txtGet = filePath +"PRI12trnreport.txt";
        string csvFile = filePath +"ky_turnout_precincts__primary_2012.csv";
        List<Output> outputList = new List<Output>();
        IEnumerable<string> lines = File.ReadLines(txtGet);
        string county = String.Empty;
        foreach (string line in lines)
        {
            string word1 = GetWord(line, 1);
            string word2 = GetWord(line,2);
            if (word1 == "COUNTY" && Regex.IsMatch(word2, @"^\d{3}$"))
            {
                county = GetWord(line, 3);
                Console.WriteLine(county);
                continue;
            }          
            if (!Regex.IsMatch(word1, @"^[A-Z]{1}\d{3}$")) continue;
            Output output = new();
            output.county = county;
            output.precinct = word1;           
            output.total_reg = Int32.Parse(GetWord(line,2).Replace(",",""));
            output.total_voted = Int32.Parse(GetWord(line,3).Replace(",",""));
            output.dems_reg = Int32.Parse(GetWord(line,5).Replace(",",""));
            output.dems_voted = Int32.Parse(GetWord(line,6).Replace(",",""));
            output.reps_reg = Int32.Parse(GetWord(line,8).Replace(",",""));
            output.reps_voted = Int32.Parse(GetWord(line,9).Replace(",",""));
            output.other_reg = Int32.Parse(GetWord(line,11).Replace(",",""));
            output.other_voted = Int32.Parse(GetWord(line,12).Replace(",",""));
            outputList.Add(output);
        }

        using (var writerC=new StreamWriter(csvFile))
        using (var csvC=new CsvWriter(writerC,CultureInfo.InvariantCulture))
        {
            csvC.Context.RegisterClassMap<OutputMap>();
            csvC.WriteRecords(outputList);
            csvC.Flush();
        }
               
    }

    public static string GetWord(string line,int position)
    {
        string[] words = line.Split(" ");
        int counter=0;
        foreach (string word in words)
        {
            if (word == "") continue;
            counter++;
            if (counter == position) return word;
        }
        return String.Empty;
    }


    public class Output
    {
        public string? county { get; set; }
        public string? precinct { get; set; }
        public int? total_reg { get; set; }
        public int? total_voted { get; set; }
        public int? dems_reg { get; set; }
        public int? dems_voted { get; set; }
        public int? reps_reg { get; set; }
        public int? reps_voted { get; set; }
        public int? other_reg { get; set; }
        public int? other_voted { get; set; }
    }

    public sealed class OutputMap : ClassMap<Output>
    {
        public OutputMap()
        {
            Map(m => m.county);
            Map(m => m.precinct);
            Map(m => m.total_reg);
            Map(m => m.total_voted);
            Map(m => m.dems_reg);
            Map(m => m.dems_voted);
            Map(m => m.reps_reg);
            Map(m => m.reps_voted);
            Map(m => m.other_reg);
            Map(m => m.other_voted);
        }
    }
}