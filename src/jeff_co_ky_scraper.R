library(tidyverse)
library(magrittr)

### DATA SCRAPED FROM PDF USING TABULIZER.
### TABULIZER IS FROM ROPENSCI AND DEPENDS ON RJAVA
### USE WITH CAUTION, THE PROCESS IS ANNOYING.
# library(tabulizer)
# jeff_co_official <- extract_tables('./src/Jefferson KY Gen16OfficialSOVC.pdf')
# jeff_co_official_20 <- extract_areas('./src/Jefferson KY Gen16OfficialSOVC.pdf', pages = 20)
# jeff_co_official_22 <- extract_areas('./src/Jefferson KY Gen16OfficialSOVC.pdf', pages = 22)
# jeff_co_official_26 <- extract_areas('./src/Jefferson KY Gen16OfficialSOVC.pdf', pages = 26)
# jeff_co_official_16 <- extract_areas('./src/Jefferson KY Gen16OfficialSOVC.pdf', pages = 16)
# jeff_co_official_19 <- extract_areas('./src/Jefferson KY Gen16OfficialSOVC.pdf', pages = 19)
# jeff_co_official_25 <- extract_areas('./src/Jefferson KY Gen16OfficialSOVC.pdf', pages = 25)
# jeff_co_official_24 <- extract_areas('./src/Jefferson KY Gen16OfficialSOVC.pdf', pages = 24)
# save(jeff_co_official, jeff_co_official_20, jeff_co_official_22,jeff_co_official_26,
#      jeff_co_official_16,jeff_co_official_19,jeff_co_official_25,jeff_co_official_24,
#      file = './src/scraped_jeff_co_pdf.rda')

load('./src/scraped_jeff_co_pdf.rda')

jeff_co_official_15 <- tibble('Precinct' = c('B181 - JEF', 'B182', 'B183','B184','B185','C101','C102','C103','C104','C105','C106','C108',
                                             'C109','C110','C111','C113','C115','C122','C123','C124','C125','C126','C128',
                                             'C129','C130','C131','C133','C134','C135','C136','C137','C138','C139','C141',
                                             'C142','C143','C144','C145','C146','C147','C148','C149','C150','C151','D101 - STM',
                                             'D104','D106','D108','D109','D110','D113','D114','D115'),
                              'Write-In' = as.character(c(2,6,19,0,1,2,2,8,3,3,11,4,1,1,4,0,11,7,5,6,0,7,2,4,0,4,7,6,5,10,8,4,
                                                0,2,2,0,0,1,0,0,0,0,0,0,1,4,8,8,3,4,2,13,12)))



pres_cols <- c('Precinct', 'Total Votes', 'Donald Trump', 'Hillary Clinton', 'Gary Johnson', 'Rocky De La Fuente', 'Jill Stein', 'Evan McMullin')

pres <- tibble()

for(i in 1:13){
  pres_i <- jeff_co_official[[i]][,1:ncol(jeff_co_official[[i]])-1] %>% as_tibble()
  names(pres_i) <- pres_cols
  
  pres <- bind_rows(pres, pres_i) %>% filter(!Precinct %in% c('Total','Polling','Absentee','Jurisdiction Wide'))
}

pres_2 <- tibble()

for(i in 14:25){
  pres_i <- jeff_co_official[[i]] %>% as_tibble()
  names(pres_i) <- c('Precinct','Write-In')
  
  pres_2 <- bind_rows(pres_2, pres_i) %>% filter(!Precinct %in% c('Total','Polling','Absentee','Jurisdiction Wide'))
}

jeff_co_20 <- jeff_co_official_20[[1]] %>%  as_tibble()
names(jeff_co_20) <- c('Precinct','Write-In')
jeff_co_22 <- jeff_co_official_22[[1]] %>%  as_tibble()
names(jeff_co_22) <- c('Precinct','Write-In')
jeff_co_26 <- jeff_co_official_26[[1]] %>% as_tibble()
names(jeff_co_26) <- c('Precinct','Write-In')
jeff_co_26 %<>% filter(!Precinct %in% c('Total','Polling','Absentee','Jurisdiction Wide'))
jeff_co_16 <- jeff_co_official_16[[1]] %>% as_tibble()
names(jeff_co_16) <- c('Precinct','Write-In')
jeff_co_19 <- jeff_co_official_19[[1]] %>% as_tibble()
names(jeff_co_19) <- c('Precinct','Write-In')
jeff_co_25 <- jeff_co_official_25[[1]] %>% as_tibble()
names(jeff_co_25) <- c('Precinct','Write-In')
jeff_co_24 <- jeff_co_official_24[[1]] %>% as_tibble()
names(jeff_co_24) <- c('Precinct','Write-In')

pres_2 <- bind_rows(pres_2, jeff_co_official_15, jeff_co_20, jeff_co_22,
                    jeff_co_26, jeff_co_16, jeff_co_19, jeff_co_25,jeff_co_24) %>% unique()

pres %<>% left_join(pres_2, by = 'Precinct')

us_sen <- tibble()

for(i in 26:38){
  us_sen_i <- jeff_co_official[[i]][,1:ncol(jeff_co_official[[i]])-1] %>% as_tibble()
  names(us_sen_i) <- c('Precinct', 'Total Votes', 'Rand Paul', 'Jim Gray', 'Write-In')
  
  us_sen <- bind_rows(us_sen, us_sen_i) %>% filter(!Precinct %in% c('Total','Polling','Absentee','Jurisdiction Wide'))
}

us_3 <- tibble()

for(i in 39:50){
  us_3_i <- jeff_co_official[[i]][,1:ncol(jeff_co_official[[i]])-1] %>% as_tibble()
  names(us_3_i) <- c('Precinct', 'Total Votes', 'Harold Bratcher', 'John Yarmuth', 'Write-In')
  
  us_3 <- bind_rows(us_3, us_3_i) %>% filter(!Precinct %in% c('Total','Polling','Absentee','Jurisdiction Wide'))
}

us_4 <- jeff_co_official[[51]][,1:ncol(jeff_co_official[[51]])-1] %>% as_tibble()
names(us_4) <- c('Precinct', 'Total Votes', 'Thomas Massie', 'Calvin Silde', 'Write-In')
us_4 %<>% filter(!Precinct %in% c('Total','Polling','Absentee','Jurisdiction Wide'))

sen_19 <- tibble()
for(i in 51:54){
  sen_19_i <- jeff_co_official[[i]][,1:ncol(jeff_co_official[[i]])-1] %>% as_tibble()
  names(sen_19_i) <- c('Precinct', 'Total Votes', 'Larry West', 'Morgan McGarvey', 'Write-In')
  
  sen_19 <- bind_rows(sen_19, sen_19_i) %>% filter(!Precinct %in% c('Total','Polling','Absentee','Jurisdiction Wide'))
}                 

sen_33 <- tibble()
for(i in 55:56){
  i <- jeff_co_official[[i]][,1:ncol(jeff_co_official[[i]])-1] %>% as_tibble()
  names(i) <- c('Precinct', 'Total Votes', 'Shenita Rickman', 'Gerald Neal', 'Write-In')
  
  sen_33 <- bind_rows(sen_33, i) %>% filter(!Precinct %in% c('Total','Polling','Absentee','Jurisdiction Wide'))
}

sen_35 <- tibble()
for(i in 57:59){
  i <- jeff_co_official[[i]][,1:ncol(jeff_co_official[[i]])-1] %>% as_tibble()
  names(i) <- c('Precinct', 'Total Votes', 'Denise Harper Angel', 'Write-In')
  
  sen_35 <- bind_rows(sen_35, i) %>% filter(!Precinct %in% c('Total','Polling','Absentee','Jurisdiction Wide'))
}

sen_37 <- tibble()
for(i in 60:61){
  i <- jeff_co_official[[i]][,1:ncol(jeff_co_official[[i]])-1] %>% as_tibble()
  names(i) <- c('Precinct', 'Total Votes', 'Perry Clark', 'Write-In')
  
  sen_37 <- bind_rows(sen_37, i) %>% filter(!Precinct %in% c('Total','Polling','Absentee','Jurisdiction Wide'))
}

house_df <- function(pg_num, candidates){
  dist <- jeff_co_official[[pg_num]][,1:ncol(jeff_co_official[[pg_num]])-1] %>% as_tibble()
  names(dist) <- candidates
  dist %<>% filter(!Precinct %in% c('Total','Polling','Absentee','Jurisdiction Wide'))
}

house_28 <- house_df(62, c('Precinct', 'Total Votes', 'Michael Payne', 'Charles Miller', 'Write-In'))
house_29 <- house_df(63, c('Precinct', 'Total Votes', 'Kevin Bratcher', 'Write-In'))
house_30 <- house_df(64, c('Precinct', 'Total Votes', 'Waymen Eddings', 'Tom Burch', 'Write-In'))
house_31 <- house_df(65, c('Precinct', 'Total Votes', 'Sarah Provancher', 'Steve Riggs', 'Write-In'))
house_32 <- house_df(66, c('Precinct', 'Total Votes', 'Phil Moffett', 'Write-In'))
house_33 <- house_df(67, c('Precinct', 'Total Votes', 'Jason Nemes', 'Rob Walker', 'Write-In'))
house_34 <- house_df(68, c('Precinct', 'Total Votes', 'Mary Lou Marzian', 'Write-In'))
house_35 <- house_df(69, c('Precinct', 'Total Votes', 'Jim Wayne', 'Write-In'))
house_36 <- house_df(70, c('Precinct', 'Total Votes', 'Jerry Miller', 'Write-In'))
house_37 <- house_df(71, c('Precinct', 'Total Votes', 'Mark Wilson', 'Jeffrey Donohue', 'Write-In'))
house_38 <- house_df(72, c('Precinct', 'Total Votes', 'Denver Butler', 'McKenzie Cantrell', 'Write-In'))
house_40 <- house_df(73, c('Precinct', 'Total Votes', 'George Demic', 'Dennis Horlander', 'Write-In'))
house_41 <- house_df(74, c('Precinct', 'Total Votes', 'Attica Scott', 'Write-In'))
house_42 <- house_df(75, c('Precinct', 'Total Votes', 'James Howland', 'Reginald Meeks', 'Write-In'))
house_43 <- house_df(76, c('Precinct', 'Total Votes', 'John Mark Owen', 'Darryl Owens', 'Write-In'))
house_44 <- house_df(77, c('Precinct', 'Total Votes', 'Joni Jenkins', 'Write-In'))
house_46 <- house_df(78, c('Precinct', 'Total Votes', 'Eric Crump', 'Alan Gentry', 'Write-In'))
house_48 <- house_df(79, c('Precinct', 'Total Votes', 'Ken Fleming', 'Maria Sorolis', 'Write-In'))

transform_df <- function(df, district_num, office){
  df %>% 
    gather(key = candidate, value = votes, -Precinct) %>% 
    filter(candidate != 'Total Votes') %>% 
    mutate(county = 'Jefferson', office = office, district = district_num) %>% 
    rename(precinct = Precinct)
}

parties <- read_csv('./src/candidates.csv')

ky_election <- bind_rows(
  transform_df(house_29, 29, 'State Representative'),
  transform_df(house_30, 30, 'State Representative'),
  transform_df(house_31, 31, 'State Representative'),
  transform_df(house_32, 32, 'State Representative'),
  transform_df(house_33, 33, 'State Representative'),
  transform_df(house_34, 34, 'State Representative'),
  transform_df(house_35, 35, 'State Representative'),
  transform_df(house_36, 36, 'State Representative'),
  transform_df(house_37, 37, 'State Representative'),
  transform_df(house_38, 38, 'State Representative'),
  transform_df(house_40, 40, 'State Representative'),
  transform_df(house_41, 41, 'State Representative'),
  transform_df(house_42, 42, 'State Representative'),
  transform_df(house_43, 43, 'State Representative'),
  transform_df(house_44, 44, 'State Representative'),
  transform_df(house_46, 46, 'State Representative'),
  transform_df(house_48, 48, 'State Representative'),
  transform_df(sen_19, 19, 'State Senate'),
  transform_df(sen_33, 33, 'State Senate'),
  transform_df(sen_35, 35, 'State Senate'),
  transform_df(sen_37, 37, 'State Senate'),
  transform_df(us_3, 3, 'U.S House'),
  transform_df(us_4, 4, 'U.S House'),
  transform_df(us_sen, NA, 'U.S Senate'),
  transform_df(pres, NA, 'President')
) %>% 
  left_join(parties, by = 'candidate')

write_csv(ky_election, './2016/20161108__ky__general__jefferson__precinct.csv')


# FOR AUDIT PURPOSES
# ky_election %>%
#   filter(office == 'U.S House') %>%
#   mutate(votes = as.numeric(votes)) %>%
#   group_by(candidate) %>%
#   summarize(total_votes = sum(votes))
