# ILDB Query Spec

Reference table of query categories, expected results, explanations, SQL, and the corresponding callable function name, for the RAID Indian Language Database (ildb) module.

| Category | Result | Explanation | Query | Call function |
|---|---|---|---|---|
| All | list all language names | Display all the names | `select name from language;` | `languagenames()` |
| All | Fetch all data | Display all data | `select * from ...` | |
| Count | Total number of languages | Display the total number of languages available in the DB | `SELECT COUNT(*) AS Total_Languages FROM language;` | |
| Count | Total Languages by zone | Total number of languages per zone | `SELECT sz.Zone, COUNT(ll.LanguageID) AS Total_Languages FROM language_location ll JOIN strategic_zone sz ON ll.ZoneID = sz.Zone_ID GROUP BY sz.Zone ORDER BY Total_Languages DESC;` | |
| Count | Organization Based Count | Total number of languages each organization is working on | `SELECT Organization, COUNT(*) TotalLanguages FROM Language GROUP BY Organization ORDER BY TotalLanguages DESC;` | |
| Count | Count by script | Number of languages written in each script | `SELECT script, COUNT(*) AS Total FROM language GROUP BY script ORDER BY Total DESC;` | |
| Count | State wise count | Total number of languages spoken in each state | `SELECT s.State_Name, COUNT(ll.LanguageID) AS Total_Languages FROM language_location ll JOIN state s ON ll.StateID = s.State_ID GROUP BY s.State_Name ORDER BY Total_Languages DESC;` | |
| Count | Total Spoken languages | Total living (currently spoken) languages | `SELECT COUNT(*) AS Spoken_Languages FROM language WHERE Lg_Status = 'Spoken';` | |
| Count | Total Extinct languages | Total extinct languages | `SELECT COUNT(*) AS Extinct_Languages FROM language WHERE Lg_Status = 'Extinct';` | |
| Count | Count by language family | Total number of languages per language family | `SELECT lg_family, COUNT(*) AS Total FROM language GROUP BY lg_family ORDER BY Total DESC;` | |
| Literacy (L1 & L2) | Low L1 literacy (<50) | Languages where <50% of native speakers can read/write in their own language | `SELECT l.language_name, li.Literacy_L1 FROM language l JOIN literacy li ON l.language_ID = li.language_ID WHERE li.Literacy_L1 < 50 ORDER BY li.Literacy_L1;` | |
| Literacy (L1 & L2) | High L1 literacy (>50) | Languages where >50% of native speakers are literate in own language | `SELECT l.language_name, li.Literacy_L1 FROM language l JOIN literacy li ON l.language_ID = li.language_ID WHERE li.Literacy_L1 > 50 ORDER BY li.Literacy_L1;` | |
| Literacy (L1 & L2) | High L2 literacy (>50) | Languages where >50% of speakers are literate in a second language | `SELECT l.language_name, li.Literacy_L2 FROM language l JOIN literacy li ON l.language_ID = li.language_ID WHERE li.Literacy_L2 > 50 ORDER BY li.Literacy_L2;` | |
| Literacy (L1 & L2) | Low L2 literacy (<50) | Languages where <50% of speakers are literate in a second language | `SELECT l.language_name, li.Literacy_L2 FROM language l JOIN literacy li ON l.language_ID = li.language_ID WHERE li.Literacy_L2 < 50 ORDER BY li.Literacy_L2;` | |
| Lg_status | List all sign languages | All sign languages | `SELECT language_name FROM language WHERE Lg_Status = 'Sign language' ORDER BY language_name;` | `sign_language()` |
| Lg_status | List all spoken languages | All living spoken languages | `SELECT language_name FROM language WHERE Lg_Status = 'Spoken' ORDER BY language_name;` | `spoken_language()` |
| Lg_status | List of extinct languages | All extinct languages | `SELECT language_name FROM language WHERE Lg_Status = 'Extinct';` | `extinct_language()` |
| Population | Population above 10 Million | Languages with >10M speakers | `SELECT l.language_name, p.population FROM language l JOIN population p ON l.language_ID = p.Language_ID WHERE p.population > 10000000 ORDER BY p.population DESC;` | `population>1M()` |
| Population | Top 10 Largest Languages | Ten languages with highest speaker count | `SELECT l.language_name, p.population FROM language l JOIN population p ON l.language_ID = p.Language_ID ORDER BY p.population DESC LIMIT 10;` | `top 10 languages()` |
| Population | Least Populated Languages | Languages with smallest speaker populations | `SELECT l.language_name, p.population FROM language l JOIN population p ON l.language_ID = p.Language_ID ORDER BY p.population LIMIT 10;` | `least languages()` |
| Population | High population, low literacy | Large speaker base but low L1 literacy (<50), pop >10M | `SELECT l.language_name, p.population, li.Literacy_L1 FROM language l JOIN population p ON l.language_ID = p.Language_ID JOIN literacy li ON l.language_ID = li.language_ID WHERE p.population > 10000000 AND li.Literacy_L1 < 50 ORDER BY p.population DESC;` | `population>1M and literacy<50()` |
| Population | Endangered languages (EGIDS 8a/8b/9) | Languages at risk per EGIDS scale | `SELECT l.language_name, e.EGIDS_level FROM language l JOIN egids_level e ON l.language_ID = e.LanguageID WHERE e.EGIDS_level IN ('8a','8b','9') ORDER BY e.EGIDS_level;` | `endangered languages()` |
| Zones | South Zone languages | Languages in South zone | `SELECT l.language_name FROM language l INNER JOIN language_location ll ON l.language_ID = ll.LanguageID INNER JOIN strategic_zone sz ON ll.ZoneID = sz.Zone_ID WHERE sz.Zone = 'South Zone' ORDER BY l.language_name;` | `south_zone()` |
| Zones | North Zone languages | Languages in North zone | `... WHERE sz.Zone = 'North Zone' ...` | `north_zone()` |
| Zones | West Zone languages | Languages in West zone | `... WHERE sz.Zone = 'West Zone' ...` | `west_zone()` |
| Zones | East Zone languages | Languages in East zone | `... WHERE sz.Zone = 'East Zone' ...` | `east_zone()` |
| Zones | North East Zone languages | Languages in North East zone | `... WHERE sz.Zone = 'North East Zone' ...` | `northeast_zone()` |
| Zones | North West Zone languages | Languages in North West zone | `... WHERE sz.Zone = 'North West Zone' ...` | `northwest_zone()` |
| Zones | Central Zone languages | Languages in Central zone | `... WHERE sz.Zone = 'Central Zone' ...` | `central_zone()` |
| Zones | Hindi Zone languages | Languages in Hindi zone | `... WHERE sz.Zone = 'Hindi Zone' ...` | `Hindi_zone()` |
| Empty/NA/duplicate | ISO code duplicates | Count of languages sharing the same ISO code | `SELECT ISO_CODE, COUNT(*) FROM language GROUP BY ISO_CODE HAVING COUNT(*)>1;` | |
| Empty/NA/duplicate | Missing ISO Code | Languages with no ISO code | `SELECT * FROM Language WHERE ISO_Code='';` | |
| Empty/NA/duplicate | Missing population | Languages with no population data | `SELECT * FROM Language WHERE population='';` | |
| Empty/NA/duplicate | No need for translation | Languages flagged as not needing translation | `SELECT * FROM Translation_project WHERE BT_status='No need';` | |
| Empty/NA/duplicate | No EGIDS | Languages with no EGIDS value | `SELECT * FROM Language WHERE EGIDS='';` | |
| Empty/NA/duplicate | No script | Languages with no script listed | `SELECT * FROM Language WHERE Script='';` | |
| Empty/NA/duplicate | No language family | Languages with no language family listed | `SELECT * FROM Language WHERE lg_family='';` | |
| BT Info | Languages with whole Bible | Languages with complete OT+NT | `SELECT l.language_name FROM language l INNER JOIN translation_project ll ON l.language_ID = ll.Language_ID WHERE scripture_status='whole Bible' ORDER BY l.language_name;` | `Bible_available()` |
| BT Info | Languages with NT | Languages with the New Testament | `SELECT l.language_name FROM language l INNER JOIN translation_project ll ON l.language_ID = ll.Language_ID WHERE scripture_status='New Testament' ORDER BY l.language_name;` | `NT_available()` |
| BT Info | Languages with project initiated | Translation work started but not complete | `SELECT l.language_name FROM language l INNER JOIN translation_project ll ON l.language_ID = ll.Language_ID WHERE bt_status='project initiated' ORDER BY l.language_name;` | `project_initiated()` |
| BT Info | Languages without scripture | No Scripture translated at all (highest priority) | `SELECT l.language_name FROM language l INNER JOIN translation_project ll ON l.language_ID = ll.Language_ID WHERE scripture_status='no scripture' ORDER BY l.language_name;` | `no_scripture()` |
| BT Info | Organization based language list | Languages grouped by organization | `SELECT Organization, GROUP_CONCAT(LanguageName ORDER BY LanguageName) FROM Language GROUP BY Organization;` | `organization()` |
| BT Info | Other media available | Additional resources per language (audio, video, JESUS Film, app, etc.) | `SELECT LanguageName, OtherMedia FROM Language WHERE OtherMedia IS NOT NULL AND OtherMedia<>'';` | `no_media()` |
| BT Info | Languages with NT but no complete Bible | NT done, OT still in progress | `SELECT l.language_name FROM language l INNER JOIN translation_project ll ON l.language_ID = ll.Language_ID WHERE bt_status='OT in progress' ORDER BY l.language_name;` | `OT_in_progress()` |
| BT Info | Languages without NT | Only Scripture portions available | `SELECT l.language_name FROM language l INNER JOIN translation_project ll ON l.language_ID = ll.Language_ID WHERE scripture_status='portions' ORDER BY l.language_name;` | `portions_available()` |
| BT Info | Research needed languages | Need further linguistic/community research before translation | `SELECT l.language_name FROM language l INNER JOIN translation_project ll ON l.language_ID = ll.Language_ID WHERE bt_status='Research needed' ORDER BY l.language_name;` | `research_needed()` |
| BT Info | No need languages | Languages not required for translation | `SELECT l.language_name FROM language l INNER JOIN translation_project ll ON l.language_ID = ll.Language_ID WHERE bt_status='no need' ORDER BY l.language_name;` | `no_need()` |

**Referenced tables:** `language`, `language_location`, `strategic_zone`, `state`, `literacy`, `population`, `egids_level`, `translation_project`.

**Status:** design/reference only — not yet implemented as callable functions in `raid_system`.
