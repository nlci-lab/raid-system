"""Build languages.db: 100 languages of India with linguistic reference data.

Speaker figures for the 22 Eighth Schedule languages and for the larger
non-scheduled mother tongues (Bhojpuri, Rajasthani, Chhattisgarhi, Magahi,
Haryanvi, Marwari, Awadhi, Bhili/Bhilodi, Gondi, Tulu, Garo, Khasi) are taken
from the Census of India 2011 language tables. Classical-language grant years
follow the Ministry of Culture notifications (2004-2014, and the October 2024
Cabinet decision adding Marathi, Pali, Prakrit, Assamese and Bengali).
Endangerment categories follow UNESCO's Atlas of the World's Languages in
Danger (2010). Figures for smaller/unscheduled languages are Ethnologue-style
estimates and should be treated as approximate.
"""

import sqlite3
from pathlib import Path

DB_DIR = Path(__file__).parent.parent.parent / "db"
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "languages.db"

CENSUS = "Census of India 2011"
ETHNOLOGUE = "Ethnologue (SIL), est."
UNESCO = "UNESCO Atlas of the World's Languages in Danger (2010)"

FAMILIES = [
    ("Indo-European", "Represented in India chiefly by the Indo-Aryan branch, descended from Old Indo-Aryan (Vedic/Classical Sanskrit); also includes Dardic languages such as Kashmiri and Shina. The largest language family in India by speaker count."),
    ("Dravidian", "A family largely confined to South Asia, with four major branches (South, South-Central, Central, North Dravidian). Includes the classical literary languages Tamil, Telugu, Kannada and Malayalam."),
    ("Austroasiatic", "In India represented by the Munda branch (Santali, Mundari, Ho, Kharia, Korku, Sora, Juang, etc.) in the eastern/central tribal belt, and the Khasic and Nicobarese branches in the Northeast and Andaman & Nicobar Islands."),
    ("Sino-Tibetan", "Represented in India by numerous Tibeto-Burman languages of the Himalayas and Northeast, including the Bodo-Garo, Kuki-Chin, Naga, Tani and Tibetic groups."),
    ("Great Andamanese", "A small, now nearly extinct family indigenous to the Andaman Islands, generally treated as a language isolate family unrelated to any mainland Indian family."),
    ("Ongan", "Also called Angan or South Andamanese; comprises Onge and Jarawa (and, by some classifications, Sentinelese), spoken by indigenous Andamanese communities and unrelated to Great Andamanese."),
    ("Tai-Kadai", "A family centred on mainland Southeast Asia and southern China; represented in India by a handful of Tai (Shan-related) languages such as Khamti, Aiton and Phake spoken by migrant Buddhist communities of eastern Assam and Arunachal Pradesh."),
    ("Language isolate", "A language with no demonstrated relationship to any other known language or family. India's sole confirmed example is Nihali, spoken in the Maharashtra-Madhya Pradesh border area."),
]

SCRIPTS = [
    ("Devanagari", "Abugida", "Left-to-right Brahmic abugida used for Hindi, Marathi, Nepali, Sanskrit, Konkani, Bodo, Dogri and many other North/Central Indian languages."),
    ("Bengali-Assamese", "Abugida", "Brahmic abugida used for Bengali, Assamese, Bishnupriya Manipuri and Meitei (alongside Meitei Mayek)."),
    ("Gujarati", "Abugida", "Brahmic abugida derived from Devanagari (without the horizontal head-line), used to write Gujarati."),
    ("Gurmukhi", "Abugida", "Brahmic abugida standardised by the Sikh Gurus, used to write Punjabi in India."),
    ("Odia script", "Abugida", "Brahmic abugida with distinctive rounded letterforms, used to write Odia."),
    ("Tamil script", "Abugida", "Brahmic abugida with a comparatively small letter inventory, used to write Tamil and some minor Dravidian languages of Tamil Nadu."),
    ("Telugu script", "Abugida", "Brahmic abugida closely related to Kannada script, used to write Telugu and several minor South-Central Dravidian languages."),
    ("Kannada script", "Abugida", "Brahmic abugida closely related to Telugu script, used to write Kannada, Tulu and Kodava."),
    ("Malayalam script", "Abugida", "Brahmic abugida used to write Malayalam, with a large conjunct-consonant inventory."),
    ("Perso-Arabic", "Abjad/alphabet", "Arabic-derived script written right-to-left, used (usually in Nastaliq style) for Urdu, Kashmiri and Sindhi."),
    ("Meitei Mayek", "Abugida", "Indigenous Brahmic-derived script of Manipur, used to write Meitei (Manipuri) alongside Bengali script."),
    ("Ol Chiki", "Alphabet", "Script devised in 1925 by Pandit Raghunath Murmu specifically for Santali."),
    ("Tibetan script", "Abugida", "Brahmic-derived abugida used to write Tibetic languages such as Ladakhi and Bhutia/Sikkimese."),
    ("Lepcha script", "Abugida", "Brahmic-derived script devised for Lepcha, used in Sikkim and West Bengal."),
    ("Chakma script", "Abugida", "Brahmic-derived script, related to Burmese/Mon scripts, used for the Chakma language."),
    ("Warang Citi", "Alphabet", "Script devised for Ho in the 20th century by Lako Bodra."),
    ("Latin script", "Alphabet", "Roman alphabet adopted (via Christian missionary orthographies) for most Northeast Indian languages such as Khasi, Garo, Mizo and the Naga languages."),
    ("Unwritten / no standard script", "N/A", "Language with no widely used indigenous or adopted writing system; transmitted orally."),
]

# name, native_name, iso_639_1, iso_639_3, family, branch, script, word_order,
# classification, is_classical, classical_since, speakers_approx, census_year,
# source, primary_regions, status, endangerment, notes
LANGUAGES = [
    ("Hindi", "हिन्दी", "hi", "hin", "Indo-European", "Indo-Aryan (Central)", "Devanagari", "SOV", "Scheduled", 0, None, 528347193, 2011, CENSUS, "Uttar Pradesh, Bihar, MP, Rajasthan, Delhi and much of the Hindi Belt", "Official language of the Union", None, "Largest mother-tongue group in India; the 2011 figure includes numerous dialects/mother tongues (e.g. Bhojpuri speakers who separately self-identify are counted individually)."),
    ("Bengali", "বাংলা", "bn", "ben", "Indo-European", "Indo-Aryan (Eastern)", "Bengali-Assamese", "SOV", "Scheduled, Classical (2024)", 1, 2024, 97237669, 2011, CENSUS, "West Bengal, Tripura", "Official (West Bengal, Tripura)", None, "Second most-spoken scheduled language; granted classical status in October 2024."),
    ("Marathi", "मराठी", "mr", "mar", "Indo-European", "Indo-Aryan (Southern)", "Devanagari", "SOV", "Scheduled, Classical (2024)", 1, 2024, 83026680, 2011, CENSUS, "Maharashtra, Goa", "Official (Maharashtra)", None, "Granted classical status in October 2024 alongside Pali, Prakrit, Assamese and Bengali."),
    ("Telugu", "తెలుగు", "te", "tel", "Dravidian", "South-Central Dravidian", "Telugu script", "SOV", "Scheduled, Classical (2008)", 1, 2008, 81127740, 2011, CENSUS, "Andhra Pradesh, Telangana", "Official (Andhra Pradesh, Telangana)", None, None),
    ("Tamil", "தமிழ்", "ta", "tam", "Dravidian", "Southern Dravidian", "Tamil script", "SOV", "Scheduled, Classical (2004)", 1, 2004, 69026881, 2011, CENSUS, "Tamil Nadu, Puducherry", "Official (Tamil Nadu, Puducherry)", None, "India's first language to be granted classical status (2004)."),
    ("Gujarati", "ગુજરાતી", "gu", "guj", "Indo-European", "Indo-Aryan (Western)", "Gujarati", "SOV", "Scheduled", 0, None, 55492554, 2011, CENSUS, "Gujarat, Dadra & Nagar Haveli and Daman & Diu", "Official (Gujarat)", None, None),
    ("Urdu", "اردو", "ur", "urd", "Indo-European", "Indo-Aryan (Central)", "Perso-Arabic", "SOV", "Scheduled", 0, None, 50772631, 2011, CENSUS, "Jammu & Kashmir, Telangana, Uttar Pradesh, Bihar", "Official in several states", None, "Shares a common spoken base with Hindi (Hindustani) but a distinct literary register, vocabulary and script."),
    ("Kannada", "ಕನ್ನಡ", "kn", "kan", "Dravidian", "Southern Dravidian", "Kannada script", "SOV", "Scheduled, Classical (2008)", 1, 2008, 43706512, 2011, CENSUS, "Karnataka", "Official (Karnataka)", None, None),
    ("Odia", "ଓଡ଼ିଆ", "or", "ori", "Indo-European", "Indo-Aryan (Eastern)", "Odia script", "SOV", "Scheduled, Classical (2014)", 1, 2014, 37521324, 2011, CENSUS, "Odisha", "Official (Odisha)", None, None),
    ("Malayalam", "മലയാളം", "ml", "mal", "Dravidian", "Southern Dravidian", "Malayalam script", "SOV", "Scheduled, Classical (2013)", 1, 2013, 34838819, 2011, CENSUS, "Kerala, Lakshadweep", "Official (Kerala, Puducherry)", None, None),
    ("Punjabi", "ਪੰਜਾਬੀ", "pa", "pan", "Indo-European", "Indo-Aryan (Northwestern)", "Gurmukhi", "SOV", "Scheduled", 0, None, 33124726, 2011, CENSUS, "Punjab, Chandigarh, Haryana", "Official (Punjab)", None, "Written in Gurmukhi in India; written in Shahmukhi (Perso-Arabic) in Pakistan."),
    ("Bhojpuri", "भोजपुरी", None, "bho", "Indo-European", "Indo-Aryan (Eastern)", "Devanagari", "SOV", "Non-Scheduled", 0, None, 50580000, 2011, CENSUS, "Bihar, Uttar Pradesh, Jharkhand", "Not an official state language; long-standing demand for Eighth Schedule inclusion", None, "Largest mother-tongue not in the Eighth Schedule; classified under Hindi in census groupings."),
    ("Assamese", "অসমীয়া", "as", "asm", "Indo-European", "Indo-Aryan (Eastern)", "Bengali-Assamese", "SOV", "Scheduled, Classical (2024)", 1, 2024, 15311351, 2011, CENSUS, "Assam", "Official (Assam)", None, None),
    ("Maithili", "मैथिली", "mai", "mai", "Indo-European", "Indo-Aryan (Eastern)", "Devanagari", "SOV", "Scheduled", 0, None, 13583464, 2011, CENSUS, "Bihar, Jharkhand", "Official (Bihar)", None, "Historically written in the Tirhuta script; Devanagari is now standard."),
    ("Magahi", "मगही", None, "mag", "Indo-European", "Indo-Aryan (Eastern)", "Devanagari", "SOV", "Non-Scheduled", 0, None, 12710000, 2011, CENSUS, "Bihar, Jharkhand", "Not an official state language", None, None),
    ("Haryanvi", "हरियाणवी", None, "bgc", "Indo-European", "Indo-Aryan (Central)", "Devanagari", "SOV", "Non-Scheduled", 0, None, 9807000, 2011, CENSUS, "Haryana", "Not an official state language", None, None),
    ("Chhattisgarhi", "छत्तीसगढ़ी", None, "hne", "Indo-European", "Indo-Aryan (Eastern)", "Devanagari", "SOV", "Non-Scheduled", 0, None, 16250000, 2011, CENSUS, "Chhattisgarh", "Second official language of Chhattisgarh", None, None),
    ("Santali", "ᱥᱟᱱᱛᱟᱲᱤ", None, "sat", "Austroasiatic", "Munda", "Ol Chiki", "SOV", "Scheduled", 0, None, 7368192, 2011, CENSUS, "Jharkhand, West Bengal, Odisha, Bihar, Assam", "Official (Jharkhand)", None, "Largest Austroasiatic language in India; also written in Devanagari and Bengali script."),
    ("Kashmiri", "कॉशुर / كٲشُر", "ks", "kas", "Indo-European", "Indo-Aryan (Dardic)", "Perso-Arabic", "SVO", "Scheduled", 0, None, 6797587, 2011, CENSUS, "Jammu & Kashmir", "Official (Jammu & Kashmir)", None, "Unusually for a Dardic/Indo-Aryan language, Kashmiri has verb-second (V2) word order in main clauses."),
    ("Marwari", "मारवाड़ी", None, "mwr", "Indo-European", "Indo-Aryan (Western, Rajasthani)", "Devanagari", "SOV", "Non-Scheduled", 0, None, 7832000, 2011, CENSUS, "Rajasthan (Marwar/Jodhpur region)", "Not an official state language", None, "Historically also written in the Mahajani mercantile script."),
    ("Nepali", "नेपाली", "ne", "nep", "Indo-European", "Indo-Aryan (Eastern Pahari)", "Devanagari", "SOV", "Scheduled", 0, None, 2926168, 2011, CENSUS, "Sikkim, West Bengal (Darjeeling), Assam", "Official (Sikkim, West Bengal-Darjeeling)", None, None),
    ("Gondi", "गोंडी", None, "gon", "Dravidian", "South-Central Dravidian", "Devanagari / Gunjala Gondi", "SOV", "Non-Scheduled", 0, None, 2857000, 2011, CENSUS, "Madhya Pradesh, Chhattisgarh, Maharashtra, Telangana", "Not an official state language; long-standing demand for Eighth Schedule inclusion", "Vulnerable", "Largest Dravidian language spoken outside the four major southern states."),
    ("Sindhi", "سنڌي / सिन्धी", "sd", "snd", "Indo-European", "Indo-Aryan (Northwestern)", "Perso-Arabic / Devanagari", "SOV", "Scheduled", 0, None, 2772264, 2011, CENSUS, "Gujarat, Maharashtra, Rajasthan (post-Partition diaspora)", "Scheduled but has no associated Indian state/territory", None, None),
    ("Dogri", "डोगरी", "doi", "dgo", "Indo-European", "Indo-Aryan (Northwestern)", "Devanagari", "SOV", "Scheduled", 0, None, 2596767, 2011, CENSUS, "Jammu region of Jammu & Kashmir", "Official (Jammu & Kashmir)", None, "Historically written in the Dogra Akkhar (Takri-derived) script, now largely replaced by Devanagari."),
    ("Konkani", "कोंकणी", None, "kok", "Indo-European", "Indo-Aryan (Southern)", "Devanagari", "SOV", "Scheduled", 0, None, 2256502, 2011, CENSUS, "Goa, coastal Karnataka and Maharashtra", "Official (Goa)", "Vulnerable", "Also written in Kannada, Malayalam, Perso-Arabic and Roman scripts depending on community."),
    ("Tulu", "ತುಳು", None, "tcy", "Dravidian", "Southern Dravidian", "Kannada script", "SOV", "Non-Scheduled", 0, None, 1842000, 2011, CENSUS, "Coastal Karnataka (Tulu Nadu), northern Kerala", "Not an official state language", "Vulnerable", "Historically had its own Tigalari script, now largely written in Kannada script."),
    ("Meitei (Manipuri)", "ꯃꯤꯇꯩꯂꯣꯟ", None, "mni", "Sino-Tibetan", "Tibeto-Burman (Kuki-Chin-Meitei)", "Meitei Mayek / Bengali-Assamese", "SOV", "Scheduled", 0, None, 1761079, 2011, CENSUS, "Manipur", "Official (Manipur)", None, "Meitei Mayek script was revived in the late 20th century after centuries of Bengali-script dominance."),
    ("Bodo", "बड़ो", None, "brx", "Sino-Tibetan", "Tibeto-Burman (Bodo-Garo)", "Devanagari", "SOV", "Scheduled", 0, None, 1482929, 2011, CENSUS, "Assam (Bodoland Territorial Region)", "Official (Assam)", None, None),
    ("Garo", "আচিক / A·chik", None, "grt", "Sino-Tibetan", "Tibeto-Burman (Bodo-Garo)", "Latin script", "SVO", "Non-Scheduled", 0, None, 1125000, 2011, CENSUS, "Meghalaya (Garo Hills)", "Associate official status in Meghalaya", None, None),
    ("Khasi", "খাসি", None, "kha", "Austroasiatic", "Khasian", "Latin script", "SVO", "Non-Scheduled", 0, None, 1038000, 2011, CENSUS, "Meghalaya (Khasi Hills)", "Associate official status in Meghalaya", None, "One of the few Austroasiatic languages with SVO (rather than SOV) word order."),
    ("Sanskrit", "संस्कृतम्", "sa", "san", "Indo-European", "Indo-Aryan (Old Indo-Aryan)", "Devanagari", "Free/SOV-default", "Scheduled, Classical (2005)", 1, 2005, 24821, 2011, CENSUS, "Pan-India (liturgical, revival communities e.g. Mattur, Karnataka)", "Official (Uttarakhand); liturgical language of Hinduism, Buddhism and Jainism", None, "Classical/liturgical language whose everyday-speaker figure is far smaller than its cultural and liturgical reach; a highly inflected language with largely free word order."),
    ("Awadhi", "अवधी", None, "awa", "Indo-European", "Indo-Aryan (Central)", "Devanagari", "SOV", "Non-Scheduled", 0, None, 3851000, 2011, CENSUS, "Central and eastern Uttar Pradesh (Awadh region)", "Not an official state language", None, "Language of major devotional works including Tulsidas's Ramcharitmanas."),
    ("Bhili/Bhilodi", "भीली", None, "bhb", "Indo-European", "Indo-Aryan (Bhil)", "Devanagari", "SOV", "Non-Scheduled", 0, None, 3207000, 2011, CENSUS, "Gujarat, Madhya Pradesh, Rajasthan, Maharashtra", "Not an official state language", "Vulnerable", "'Bhili/Bhilodi' is a census umbrella label covering a cluster of closely related Bhil mother tongues."),
    ("Rajasthani", "राजस्थानी", None, "raj", "Indo-European", "Indo-Aryan (Western)", "Devanagari", "SOV", "Non-Scheduled", 0, None, 25810000, 2011, CENSUS, "Rajasthan", "Not an official state language; long-standing demand for Eighth Schedule inclusion", None, "Census umbrella label; speakers of named Rajasthani varieties such as Marwari and Mewari are counted separately."),
    ("Mewari", "मेवाड़ी", None, "mtr", "Indo-European", "Indo-Aryan (Western, Rajasthani)", "Devanagari", "SOV", "Non-Scheduled", 0, None, 5000000, None, ETHNOLOGUE, "Rajasthan (Mewar/Udaipur region)", "Not an official state language", None, None),
    ("Malvi", "मालवी", None, "mup", "Indo-European", "Indo-Aryan (Western, Rajasthani)", "Devanagari", "SOV", "Non-Scheduled", 0, None, 5500000, None, ETHNOLOGUE, "Madhya Pradesh (Malwa region), Rajasthan", "Not an official state language", None, None),
    ("Nimadi", "निमाड़ी", None, "noe", "Indo-European", "Indo-Aryan (Western)", "Devanagari", "SOV", "Non-Scheduled", 0, None, 2100000, None, ETHNOLOGUE, "Madhya Pradesh (Nimar region)", "Not an official state language", "Vulnerable", None),
    ("Khandeshi", "खानदेशी", None, "khn", "Indo-European", "Indo-Aryan (Bhil)", "Devanagari", "SOV", "Non-Scheduled", 0, None, 1860000, None, ETHNOLOGUE, "Maharashtra (Khandesh region)", "Not an official state language", "Vulnerable", None),
    ("Lambadi (Banjari)", "लमाणी / लंबाडी", None, "lmn", "Indo-European", "Indo-Aryan (Western, Rajasthani-related)", "Devanagari / Telugu", "SOV", "Non-Scheduled", 0, None, 3300000, None, ETHNOLOGUE, "Karnataka, Andhra Pradesh, Telangana, Maharashtra", "Not an official state language", "Vulnerable", "Language of the historically itinerant Banjara (Lambadi) trading community, spoken across many states."),
    ("Halbi", "हल्बी", None, "hlb", "Indo-European", "Indo-Aryan (Southern, Marathi-related)", "Devanagari", "SOV", "Non-Scheduled", 0, None, 700000, None, ETHNOLOGUE, "Chhattisgarh (Bastar region), Odisha", "Not an official state language", "Vulnerable", "Used historically as a lingua franca among tribal groups of the Bastar region."),
    ("Bundeli", "बुंदेली", None, "bns", "Indo-European", "Indo-Aryan (Central)", "Devanagari", "SOV", "Non-Scheduled", 0, None, 8000000, None, ETHNOLOGUE, "Madhya Pradesh, Uttar Pradesh (Bundelkhand region)", "Not an official state language", None, None),
    ("Braj Bhasha", "ब्रजभाषा", None, "bra", "Indo-European", "Indo-Aryan (Central)", "Devanagari", "SOV", "Non-Scheduled", 0, None, 574000, None, ETHNOLOGUE, "Western Uttar Pradesh (Braj region)", "Not an official state language", "Vulnerable", "Major medieval literary language of Krishna-devotional (bhakti) poetry."),
    ("Kumaoni", "कुमाऊँनी", None, "kfy", "Indo-European", "Indo-Aryan (Pahari)", "Devanagari", "SOV", "Non-Scheduled", 0, None, 2000000, None, ETHNOLOGUE, "Uttarakhand (Kumaon region)", "Not an official state language", "Vulnerable", None),
    ("Garhwali", "गढ़वळि", None, "gbm", "Indo-European", "Indo-Aryan (Pahari)", "Devanagari", "SOV", "Non-Scheduled", 0, None, 2300000, None, ETHNOLOGUE, "Uttarakhand (Garhwal region)", "Not an official state language", "Vulnerable", None),
    ("Angika", "अंगिका", None, "anp", "Indo-European", "Indo-Aryan (Eastern, Bihari)", "Devanagari", "SOV", "Non-Scheduled", 0, None, 7600000, None, ETHNOLOGUE, "Bihar, Jharkhand (Anga region)", "Not an official state language", None, None),
    ("Bajjika", "बज्जिका", None, "vjk", "Indo-European", "Indo-Aryan (Eastern, Bihari)", "Devanagari", "SOV", "Non-Scheduled", 0, None, 7900000, None, ETHNOLOGUE, "Bihar (Vaishali/Muzaffarpur region)", "Not an official state language", None, None),
    ("Surjapuri", "सुरजापुरी", None, "sjp", "Indo-European", "Indo-Aryan (Eastern)", "Devanagari", "SOV", "Non-Scheduled", 0, None, 2400000, None, ETHNOLOGUE, "Bihar, West Bengal, Jharkhand (Purnia/Kishanganj region)", "Not an official state language", None, None),
    ("Nagpuri (Sadri)", "नागपुरी / सादरी", None, "sck", "Indo-European", "Indo-Aryan (Eastern, Bihari)", "Devanagari", "SOV", "Non-Scheduled", 0, None, 5100000, None, ETHNOLOGUE, "Jharkhand (Chota Nagpur Plateau)", "Not an official state language", None, "Widely used as a tribal-belt lingua franca in Jharkhand."),
    ("Khortha", "खोरठा", None, "khb", "Indo-European", "Indo-Aryan (Eastern, Bihari)", "Devanagari", "SOV", "Non-Scheduled", 0, None, 8000000, None, ETHNOLOGUE, "Jharkhand (Chota Nagpur Plateau)", "Not an official state language", None, None),
    ("Kurmali", "कुड़माली", None, "kyw", "Indo-European", "Indo-Aryan (Eastern, Bihari)", "Devanagari", "SOV", "Non-Scheduled", 0, None, 500000, None, ETHNOLOGUE, "Jharkhand, West Bengal", "Not an official state language", "Vulnerable", None),
    ("Panchpargania", "पंचपरगनिया", None, "tdb", "Indo-European", "Indo-Aryan (Eastern, Bihari)", "Devanagari", "SOV", "Non-Scheduled", 0, None, 280000, None, ETHNOLOGUE, "Jharkhand (Ranchi region)", "Not an official state language", "Vulnerable", None),
    ("Kui", "କୁଇ", None, "kxu", "Dravidian", "South-Central Dravidian", "Odia script", "SOV", "Non-Scheduled", 0, None, 940000, None, ETHNOLOGUE, "Odisha (Kandhamal, Koraput)", "Not an official state language", "Vulnerable", "Principal language of the Kondh (Kandha) tribal community."),
    ("Kuvi", "କୁୱି", None, "kxv", "Dravidian", "South-Central Dravidian", "Odia script", "SOV", "Non-Scheduled", 0, None, 130000, None, ETHNOLOGUE, "Odisha, Andhra Pradesh", "Not an official state language", "Vulnerable", None),
    ("Koya", "కోయ", None, "kff", "Dravidian", "South-Central Dravidian", "Telugu script", "SOV", "Non-Scheduled", 0, None, 410000, None, ETHNOLOGUE, "Telangana, Andhra Pradesh, Chhattisgarh", "Not an official state language", "Vulnerable", None),
    ("Kolami", "कोलामी", None, "kfb", "Dravidian", "Central Dravidian", "Devanagari", "SOV", "Non-Scheduled", 0, None, 130000, None, ETHNOLOGUE, "Maharashtra, Telangana", "Not an official state language", "Endangered", None),
    ("Kurukh (Oraon)", "कुड़ुख़", None, "kru", "Dravidian", "Northern Dravidian", "Devanagari / Kurukh Tolong Siki", "SOV", "Non-Scheduled", 0, None, 1900000, None, ETHNOLOGUE, "Jharkhand, Chhattisgarh, Odisha, West Bengal", "Not an official state language; demand for Eighth Schedule inclusion", "Vulnerable", "One of the northernmost outliers of the Dravidian family, far from the southern Dravidian heartland."),
    ("Malto", "माल्टो", None, "kmj", "Dravidian", "Northern Dravidian", "Devanagari / Bengali", "SOV", "Non-Scheduled", 0, None, 230000, None, ETHNOLOGUE, "Jharkhand, West Bengal (Rajmahal Hills)", "Not an official state language", "Endangered", None),
    ("Kodava", "ಕೊಡವ ತಕ್ಕ್", None, "kfa", "Dravidian", "Southern Dravidian", "Kannada script", "SOV", "Non-Scheduled", 0, None, 120000, None, ETHNOLOGUE, "Karnataka (Kodagu/Coorg)", "Not an official state language", "Vulnerable", None),
    ("Badaga", "படகா", None, "bfq", "Dravidian", "Southern Dravidian", "Kannada / Tamil script", "SOV", "Non-Scheduled", 0, None, 140000, None, ETHNOLOGUE, "Tamil Nadu (Nilgiri Hills)", "Not an official state language", "Vulnerable", None),
    ("Toda", "தோதா", None, "tcx", "Dravidian", "Southern Dravidian", "Tamil script", "SOV", "Non-Scheduled", 0, None, 1600, None, ETHNOLOGUE, "Tamil Nadu (Nilgiri Hills)", "Not an official state language", "Severely Endangered", "Spoken by the pastoralist Toda community of the Nilgiris; noted for an unusually large vowel and consonant inventory."),
    ("Kota", "கோத", None, "kfe", "Dravidian", "Southern Dravidian", "Tamil script", "SOV", "Non-Scheduled", 0, None, 1400, None, ETHNOLOGUE, "Tamil Nadu (Nilgiri Hills)", "Not an official state language", "Severely Endangered", None),
    ("Irula", "இருளர்", None, "iru", "Dravidian", "Southern Dravidian", "Tamil script", "SOV", "Non-Scheduled", 0, None, 200000, None, ETHNOLOGUE, "Tamil Nadu, Kerala (Nilgiris/Wayanad)", "Not an official state language", "Vulnerable", None),
    ("Yerukala", "యెరుకుల", None, "yeu", "Dravidian", "South-Central Dravidian", "Telugu script", "SOV", "Non-Scheduled", 0, None, 750000, None, ETHNOLOGUE, "Andhra Pradesh, Telangana, Tamil Nadu, Karnataka", "Not an official state language", "Vulnerable", None),
    ("Mundari", "मुंडारी", None, "unr", "Austroasiatic", "Munda", "Devanagari / Ol Chiki / Latin", "SOV", "Non-Scheduled", 0, None, 1500000, None, ETHNOLOGUE, "Jharkhand, Odisha, West Bengal", "Not an official state language", "Vulnerable", None),
    ("Ho", "होꞌ", None, "hoc", "Austroasiatic", "Munda", "Warang Citi / Devanagari", "SOV", "Non-Scheduled", 0, None, 1420000, None, ETHNOLOGUE, "Jharkhand, Odisha, West Bengal", "Not an official state language", "Vulnerable", None),
    ("Kharia", "खड़िया", None, "khr", "Austroasiatic", "Munda", "Devanagari", "SOV", "Non-Scheduled", 0, None, 300000, None, ETHNOLOGUE, "Jharkhand, Chhattisgarh, Odisha", "Not an official state language", "Vulnerable", None),
    ("Korku", "कोरकू", None, "kfq", "Austroasiatic", "Munda", "Devanagari", "SOV", "Non-Scheduled", 0, None, 720000, None, ETHNOLOGUE, "Madhya Pradesh, Maharashtra (Satpura range)", "Not an official state language", "Vulnerable", None),
    ("Sora", "सोरा", None, "srb", "Austroasiatic", "Munda", "Sorang Sompeng / Odia", "SOV", "Non-Scheduled", 0, None, 410000, None, ETHNOLOGUE, "Odisha, Andhra Pradesh", "Not an official state language", "Endangered", None),
    ("Juang", "जुआंग", None, "jun", "Austroasiatic", "Munda", "Odia script", "SOV", "Non-Scheduled", 0, None, 30000, None, ETHNOLOGUE, "Odisha (Keonjhar/Angul)", "Not an official state language", "Severely Endangered", None),
    ("Didayi (Gtaʼ)", "डिडायी", None, "gaq", "Austroasiatic", "Munda", "Odia script", "SOV", "Non-Scheduled", 0, None, 7500, None, ETHNOLOGUE, "Odisha (Malkangiri)", "Recognised as a Particularly Vulnerable Tribal Group language", "Critically Endangered", None),
    ("Car Nicobarese", "Car Nicobarese", None, "caq", "Austroasiatic", "Nicobarese", "Latin script", "SVO", "Non-Scheduled", 0, None, 19000, None, ETHNOLOGUE, "Car Nicobar, Andaman & Nicobar Islands", "Not an official territory language", "Vulnerable", None),
    ("Shompen", "Shompen", None, "sii", "Austroasiatic", "Nicobarese (disputed)", "Unwritten / no standard script", "SOV", "Non-Scheduled", 0, None, 400, None, ETHNOLOGUE, "Great Nicobar Island", "Not an official territory language", "Critically Endangered", "Spoken by one of the most isolated Particularly Vulnerable Tribal Groups in India."),
    ("Mizo (Lushai)", "Mizo ṭawng", None, "lus", "Sino-Tibetan", "Tibeto-Burman (Kuki-Chin)", "Latin script", "SOV", "Non-Scheduled", 0, None, 830000, None, ETHNOLOGUE, "Mizoram", "Official (Mizoram)", None, None),
    ("Kokborok (Tripuri)", "Kokborok", None, "trp", "Sino-Tibetan", "Tibeto-Burman (Bodo-Koch)", "Latin script (formerly Bengali)", "SOV", "Non-Scheduled", 0, None, 1050000, None, ETHNOLOGUE, "Tripura", "Official (Tripura)", None, "Long-standing demand for inclusion in the Eighth Schedule."),
    ("Karbi", "Karbi", None, "mjw", "Sino-Tibetan", "Tibeto-Burman", "Latin script", "SOV", "Non-Scheduled", 0, None, 610000, None, ETHNOLOGUE, "Assam (Karbi Anglong)", "Not an official state language", None, None),
    ("Dimasa", "Dimasa", None, "dis", "Sino-Tibetan", "Tibeto-Burman (Bodo-Garo)", "Latin script (formerly Bengali)", "SOV", "Non-Scheduled", 0, None, 140000, None, ETHNOLOGUE, "Assam (Dima Hasao), Nagaland", "Not an official state language", "Vulnerable", None),
    ("Tangkhul", "Tangkhul", None, "nmf", "Sino-Tibetan", "Tibeto-Burman (Naga)", "Latin script", "SOV", "Non-Scheduled", 0, None, 160000, None, ETHNOLOGUE, "Manipur (Ukhrul district)", "Not an official state language", None, None),
    ("Ao", "Ao", None, "njo", "Sino-Tibetan", "Tibeto-Burman (Naga)", "Latin script", "SOV", "Non-Scheduled", 0, None, 280000, None, ETHNOLOGUE, "Nagaland (Mokokchung)", "Recognised regional language of Nagaland", None, None),
    ("Angami", "Angami", None, "njm", "Sino-Tibetan", "Tibeto-Burman (Naga)", "Latin script", "SOV", "Non-Scheduled", 0, None, 150000, None, ETHNOLOGUE, "Nagaland (Kohima)", "Recognised regional language of Nagaland", None, None),
    ("Sumi (Sema)", "Sumi", None, "nsm", "Sino-Tibetan", "Tibeto-Burman (Naga)", "Latin script", "SOV", "Non-Scheduled", 0, None, 240000, None, ETHNOLOGUE, "Nagaland (Zunheboto)", "Recognised regional language of Nagaland", None, None),
    ("Lotha", "Lotha", None, "njh", "Sino-Tibetan", "Tibeto-Burman (Naga)", "Latin script", "SOV", "Non-Scheduled", 0, None, 180000, None, ETHNOLOGUE, "Nagaland (Wokha)", "Recognised regional language of Nagaland", None, None),
    ("Konyak", "Konyak", None, "nbe", "Sino-Tibetan", "Tibeto-Burman (Naga)", "Latin script", "SOV", "Non-Scheduled", 0, None, 250000, None, ETHNOLOGUE, "Nagaland (Mon), Arunachal Pradesh", "Recognised regional language of Nagaland", None, None),
    ("Adi", "Adi", None, "adi", "Sino-Tibetan", "Tibeto-Burman (Tani)", "Latin script", "SOV", "Non-Scheduled", 0, None, 230000, None, ETHNOLOGUE, "Arunachal Pradesh (Siang region)", "Not an official state language", None, None),
    ("Nyishi", "Nyishi", None, "njz", "Sino-Tibetan", "Tibeto-Burman (Tani)", "Latin script", "SOV", "Non-Scheduled", 0, None, 300000, None, ETHNOLOGUE, "Arunachal Pradesh (Papum Pare, Kra Daadi)", "Not an official state language", None, "Largest tribal community/language of Arunachal Pradesh."),
    ("Apatani", "Tanw", None, "apt", "Sino-Tibetan", "Tibeto-Burman (Tani)", "Latin script", "SOV", "Non-Scheduled", 0, None, 66000, None, ETHNOLOGUE, "Arunachal Pradesh (Ziro Valley)", "Not an official state language", "Vulnerable", None),
    ("Mising (Mishing)", "Mising", None, "mrg", "Sino-Tibetan", "Tibeto-Burman (Tani)", "Latin script", "SOV", "Non-Scheduled", 0, None, 680000, None, ETHNOLOGUE, "Assam (Brahmaputra Valley)", "Not an official state language", None, None),
    ("Ladakhi", "ལ་ཡགས་སྐད་", None, "lbj", "Sino-Tibetan", "Tibeto-Burman (Tibetic)", "Tibetan script", "SOV", "Non-Scheduled", 0, None, 130000, None, ETHNOLOGUE, "Ladakh", "Not an official Union Territory language", "Vulnerable", None),
    ("Lepcha", "ལ་ཡགས་སྐད་", None, "lep", "Sino-Tibetan", "Tibeto-Burman", "Lepcha script", "SOV", "Non-Scheduled", 0, None, 66000, None, ETHNOLOGUE, "Sikkim, West Bengal (Kalimpong/Darjeeling)", "Recognised regional language of Sikkim", "Endangered", "Indigenous language of the Lepcha people, considered the earliest inhabitants of Sikkim."),
    ("Bhutia (Sikkimese)", "འབགོ་ལ་", None, "sip", "Sino-Tibetan", "Tibeto-Burman (Tibetic)", "Tibetan script", "SOV", "Non-Scheduled", 0, None, 70000, None, ETHNOLOGUE, "Sikkim", "Recognised regional/official language of Sikkim", "Vulnerable", None),
    ("Kinnauri", "किन्नौरी", None, "kfk", "Sino-Tibetan", "Tibeto-Burman", "Devanagari", "SOV", "Non-Scheduled", 0, None, 85000, None, ETHNOLOGUE, "Himachal Pradesh (Kinnaur)", "Not an official state language", "Vulnerable", None),
    ("Lahuli (Bunan)", "लाहुली", None, "bfu", "Sino-Tibetan", "Tibeto-Burman", "Devanagari", "SOV", "Non-Scheduled", 0, None, 5000, None, ETHNOLOGUE, "Himachal Pradesh (Lahaul)", "Not an official state language", "Endangered", None),
    ("Chakma", "\U00011106\U00011127\U0001112E\U00011128\U0001112E", None, "ccp", "Indo-European", "Indo-Aryan (Eastern)", "Chakma script", "SOV", "Non-Scheduled", 0, None, 228000, None, ETHNOLOGUE, "Mizoram, Tripura, Arunachal Pradesh", "Not an official state language", "Vulnerable", None),
    ("Shina", "شینا", None, "scl", "Indo-European", "Indo-Aryan (Dardic)", "Perso-Arabic", "SOV", "Non-Scheduled", 0, None, 40000, None, ETHNOLOGUE, "Jammu & Kashmir, Ladakh (Gurez, Dras)", "Not an official Union Territory language", "Endangered", None),
    ("Konda", "కొండ", None, "kfc", "Dravidian", "South-Central Dravidian", "Telugu script", "SOV", "Non-Scheduled", 0, None, 65000, None, ETHNOLOGUE, "Andhra Pradesh, Odisha", "Not an official state language", "Endangered", None),
    ("Pali", "पालि", "pi", "pli", "Indo-European", "Indo-Aryan (Middle Indo-Aryan / Prakrit)", "Devanagari / Brahmi-derived", "SOV", "Classical (2024)", 1, 2024, 0, None, ETHNOLOGUE, "Pan-India (liturgical, Buddhist canon)", "Liturgical language of Theravada Buddhism; no native speaker community", None, "Language of the Tipitaka (Pali Canon); classical status granted October 2024."),
    ("Prakrit", "प्राकृत", None, "pra", "Indo-European", "Indo-Aryan (Middle Indo-Aryan)", "Devanagari / Brahmi-derived", "SOV", "Classical (2024)", 1, 2024, 0, None, ETHNOLOGUE, "Pan-India (liturgical, Jain canon)", "Liturgical language of Jainism; no native speaker community", None, "Umbrella term for a family of Middle Indo-Aryan vernaculars; classical status granted October 2024."),
    ("Great Andamanese", "Great Andamanese", None, "gac", "Great Andamanese", "Great Andamanese", "Unwritten / no standard script", "SOV", "Non-Scheduled", 0, None, 2, None, ETHNOLOGUE, "Strait Island, Andaman Islands", "Not an official territory language", "Critically Endangered", "Down to a handful of speakers of a mixed/composite variety; most of the ten original Great Andamanese languages are already extinct."),
    ("Onge", "Onge", None, "oon", "Ongan", "Ongan", "Unwritten / no standard script", "SOV", "Non-Scheduled", 0, None, 100, None, ETHNOLOGUE, "Little Andaman Island", "Not an official territory language", "Critically Endangered", None),
    ("Jarawa", "Jarawa", None, "anq", "Ongan", "Ongan", "Unwritten / no standard script", "SOV", "Non-Scheduled", 0, None, 380, None, ETHNOLOGUE, "South and Middle Andaman Islands", "Not an official territory language", "Critically Endangered", "Spoken by one of India's last hunter-gatherer communities to have limited contact with outsiders."),
    ("Sentinelese", "Sentinelese", None, "std", "Ongan (unclassified)", "Ongan (unclassified)", "Unwritten / no standard script", "Unknown", "Non-Scheduled", 0, None, 150, None, ETHNOLOGUE, "North Sentinel Island", "Not an official territory language", "Critically Endangered", "Spoken by an uncontacted community; the language is unclassified beyond a probable Ongan affiliation, and outside access to North Sentinel Island is prohibited by law."),
]


# Second batch of 100: languages not in the Eighth Schedule / major-language list
# above, reaching further into the Naga group, Kuki-Chin, Arunachal (Tani), Munda,
# minor Dravidian, and Himalayan Pahari languages, plus the pre-contact Great
# Andamanese languages (most now extinct) and India's one language isolate, Nihali.
# Speaker figures are Census of India 2011 where marked CENSUS; all others are
# Ethnologue-style secondary estimates (marked ETHNOLOGUE) and should be treated
# as approximate, since most of these languages are not separately tabulated in
# the census. Endangerment adds "Extinct" to the four UNESCO Atlas tiers used
# above, for the Great Andamanese varieties that have died out since 2009-2020.
LANGUAGES_BATCH_2 = [
    # -- Naga group (Sino-Tibetan, Tibeto-Burman) --
    ("Chokri Naga", "Chokri", None, "nri", "Sino-Tibetan", "Tibeto-Burman (Naga)", "Latin script", "SOV", "Non-Scheduled", 0, None, 72000, None, ETHNOLOGUE, "Nagaland (Phek)", "One of three dialects merged into the official 'Chakhesang' identity", None, "Chakhesang is a political/administrative grouping of the closely related Chokri, Kheza and Sopvoma varieties rather than a single ISO-coded language."),
    ("Rengma Naga", "Rengma", None, "nre", "Sino-Tibetan", "Tibeto-Burman (Naga)", "Latin script", "SOV", "Non-Scheduled", 0, None, 24000, None, ETHNOLOGUE, "Nagaland (Tseminyu), Assam", "Recognised regional language of Nagaland", "Vulnerable", None),
    ("Anal", "Anal", None, "anm", "Sino-Tibetan", "Tibeto-Burman (Naga-Kuki border)", "Latin script", "SOV", "Non-Scheduled", 0, None, 26000, None, ETHNOLOGUE, "Manipur (Chandel)", "Not an official state language", "Vulnerable", None),
    ("Chang Naga", "Chang", None, "nbc", "Sino-Tibetan", "Tibeto-Burman (Naga)", "Latin script", "SOV", "Non-Scheduled", 0, None, 52000, None, ETHNOLOGUE, "Nagaland (Tuensang)", "Recognised regional language of Nagaland", None, None),
    ("Phom Naga", "Phom", None, "nph", "Sino-Tibetan", "Tibeto-Burman (Naga)", "Latin script", "SOV", "Non-Scheduled", 0, None, 150000, None, ETHNOLOGUE, "Nagaland (Longleng)", "Recognised regional language of Nagaland", None, None),
    ("Yimchunger Naga", "Yimchunger", None, "yim", "Sino-Tibetan", "Tibeto-Burman (Naga)", "Latin script", "SOV", "Non-Scheduled", 0, None, 65000, None, ETHNOLOGUE, "Nagaland (Kiphire, Noklak)", "Recognised regional language of Nagaland", None, None),
    ("Khiamniungan Naga", "Khiamniungan", None, "kix", "Sino-Tibetan", "Tibeto-Burman (Naga)", "Latin script", "SOV", "Non-Scheduled", 0, None, 61983, 2011, CENSUS, "Nagaland (Noklak), Myanmar border", "Recognised regional language of Nagaland", None, None),
    ("Pochuri Naga", "Pochuri", None, "npo", "Sino-Tibetan", "Tibeto-Burman (Naga)", "Latin script", "SOV", "Non-Scheduled", 0, None, 19000, None, ETHNOLOGUE, "Nagaland (Meluri)", "Recognised regional language of Nagaland", "Vulnerable", None),
    ("Sangtam Naga", "Sangtam", None, "nsa", "Sino-Tibetan", "Tibeto-Burman (Naga)", "Latin script", "SOV", "Non-Scheduled", 0, None, 90000, None, ETHNOLOGUE, "Nagaland (Kiphire, Zunheboto)", "Recognised regional language of Nagaland", None, None),
    ("Liangmai Naga", "Liangmai", None, "njn", "Sino-Tibetan", "Tibeto-Burman (Zeliangrong)", "Latin script", "SOV", "Non-Scheduled", 0, None, 40000, None, ETHNOLOGUE, "Manipur, Nagaland (Peren)", "Not an official state language", "Vulnerable", "Part of the Zeliangrong cultural-linguistic cluster with Zeme and Rongmei."),
    ("Zeme Naga", "Zeme", None, "nzm", "Sino-Tibetan", "Tibeto-Burman (Zeliangrong)", "Latin script", "SOV", "Non-Scheduled", 0, None, 55000, None, ETHNOLOGUE, "Nagaland (Peren), Manipur, Assam", "Not an official state language", "Vulnerable", None),
    ("Poumai Naga", "Poumai", None, "pmx", "Sino-Tibetan", "Tibeto-Burman (Naga)", "Latin script", "SOV", "Non-Scheduled", 0, None, 120000, None, ETHNOLOGUE, "Manipur (Senapati)", "Not an official state language", None, None),
    ("Mao Naga", "Mao", None, "nbi", "Sino-Tibetan", "Tibeto-Burman (Naga)", "Latin script", "SOV", "Non-Scheduled", 0, None, 100000, None, ETHNOLOGUE, "Manipur (Senapati)", "Not an official state language", None, None),
    ("Rongmei (Kabui)", "Rongmei", None, "nbu", "Sino-Tibetan", "Tibeto-Burman (Zeliangrong)", "Latin script", "SOV", "Non-Scheduled", 0, None, 150000, None, ETHNOLOGUE, "Manipur, Nagaland, Assam", "Not an official state language", None, "Part of the Zeliangrong cluster with Zeme and Liangmai."),
    ("Thangal", "Thangal", None, "nki", "Sino-Tibetan", "Tibeto-Burman (Naga)", "Latin script", "SOV", "Non-Scheduled", 0, None, 15000, None, ETHNOLOGUE, "Manipur (Senapati)", "Not an official state language", "Vulnerable", None),
    ("Maring Naga", "Maring", None, "nng", "Sino-Tibetan", "Tibeto-Burman (Naga)", "Latin script", "SOV", "Non-Scheduled", 0, None, 18000, None, ETHNOLOGUE, "Manipur (Chandel, Ukhrul)", "Not an official state language", "Vulnerable", None),
    # -- Kuki-Chin group (Sino-Tibetan) --
    ("Thadou", "Thadou", None, "tcz", "Sino-Tibetan", "Tibeto-Burman (Kuki-Chin)", "Latin script", "SOV", "Non-Scheduled", 0, None, 350000, None, ETHNOLOGUE, "Manipur, Assam, Nagaland", "Not an official state language", None, "Largest of the Old Kuki languages of Manipur by speaker count."),
    ("Paite", "Paite", None, "pck", "Sino-Tibetan", "Tibeto-Burman (Kuki-Chin)", "Latin script", "SOV", "Non-Scheduled", 0, None, 110000, None, ETHNOLOGUE, "Manipur, Mizoram, Assam", "Not an official state language", None, None),
    ("Hmar", "Hmar", None, "hmr", "Sino-Tibetan", "Tibeto-Burman (Kuki-Chin)", "Latin script", "SOV", "Non-Scheduled", 0, None, 85000, None, ETHNOLOGUE, "Mizoram, Manipur, Assam, Meghalaya, Tripura", "Not an official state language", None, None),
    ("Vaiphei", "Vaiphei", None, "vap", "Sino-Tibetan", "Tibeto-Burman (Kuki-Chin)", "Latin script", "SOV", "Non-Scheduled", 0, None, 50000, None, ETHNOLOGUE, "Manipur, Mizoram, Assam", "Not an official state language", None, None),
    ("Simte", "Simte", None, "smt", "Sino-Tibetan", "Tibeto-Burman (Kuki-Chin)", "Latin script", "SOV", "Non-Scheduled", 0, None, 20000, None, ETHNOLOGUE, "Manipur", "Not an official state language", "Vulnerable", None),
    ("Zou", "Zou", None, "zom", "Sino-Tibetan", "Tibeto-Burman (Kuki-Chin)", "Latin script", "SOV", "Non-Scheduled", 0, None, 30000, None, ETHNOLOGUE, "Manipur, Mizoram", "Not an official state language", "Vulnerable", None),
    ("Gangte", "Gangte", None, "gnb", "Sino-Tibetan", "Tibeto-Burman (Kuki-Chin)", "Latin script", "SOV", "Non-Scheduled", 0, None, 15000, None, ETHNOLOGUE, "Manipur (Churachandpur)", "Not an official state language", "Vulnerable", None),
    ("Kom", "Kom", None, "kmm", "Sino-Tibetan", "Tibeto-Burman (Kuki-Chin)", "Latin script", "SOV", "Non-Scheduled", 0, None, 15000, None, ETHNOLOGUE, "Manipur", "Not an official state language", "Vulnerable", None),
    ("Aimol", "Aimol", None, "aim", "Sino-Tibetan", "Tibeto-Burman (Kuki-Chin)", "Latin script", "SOV", "Non-Scheduled", 0, None, 5000, None, ETHNOLOGUE, "Manipur (Churachandpur)", "Not an official state language", "Endangered", None),
    ("Lamkang", "Lamkang", None, "lmk", "Sino-Tibetan", "Tibeto-Burman (Kuki-Chin)", "Latin script", "SOV", "Non-Scheduled", 0, None, 9000, None, ETHNOLOGUE, "Manipur (Chandel)", "Not an official state language", "Endangered", None),
    ("Moyon", "Moyon", None, "nmo", "Sino-Tibetan", "Tibeto-Burman (Kuki-Chin)", "Latin script", "SOV", "Non-Scheduled", 0, None, 4000, None, ETHNOLOGUE, "Manipur (Chandel)", "Not an official state language", "Endangered", None),
    ("Monsang", "Monsang", None, "nmh", "Sino-Tibetan", "Tibeto-Burman (Kuki-Chin)", "Latin script", "SOV", "Non-Scheduled", 0, None, 2000, 2015, ETHNOLOGUE, "Manipur (Chandel)", "Not an official state language", "Endangered", None),
    ("Mara (Lakher)", "Mara", None, "mrh", "Sino-Tibetan", "Tibeto-Burman (Kuki-Chin)", "Latin script", "SOV", "Non-Scheduled", 0, None, 40000, None, ETHNOLOGUE, "Mizoram (Saiha)", "Recognised regional language of Mizoram", None, None),
    ("Bawm", "Bawm", None, "bgr", "Sino-Tibetan", "Tibeto-Burman (Kuki-Chin)", "Latin script", "SOV", "Non-Scheduled", 0, None, 15000, None, ETHNOLOGUE, "Mizoram, Tripura", "Not an official state language", "Vulnerable", None),
    # -- Tani / Arunachal Pradesh (Sino-Tibetan) --
    ("Galo", "Galo", None, "adl", "Sino-Tibetan", "Tibeto-Burman (Tani)", "Latin script", "SOV", "Non-Scheduled", 0, None, 29000, 2011, CENSUS, "Arunachal Pradesh (West Siang)", "Not an official state language", None, None),
    ("Tagin", "Tagin", None, "tgj", "Sino-Tibetan", "Tibeto-Burman (Tani)", "Latin script", "SOV", "Non-Scheduled", 0, None, 62897, 2011, CENSUS, "Arunachal Pradesh (Upper Subansiri)", "Not an official state language", None, None),
    ("Idu Mishmi", "Idu", None, "clk", "Sino-Tibetan", "Tibeto-Burman (Mishmi)", "Latin script", "SOV", "Non-Scheduled", 0, None, 11000, None, ETHNOLOGUE, "Arunachal Pradesh (Lower Dibang Valley)", "Not an official state language", "Vulnerable", None),
    ("Digaru Mishmi (Taraon)", "Taraon", None, "mhu", "Sino-Tibetan", "Tibeto-Burman (Mishmi)", "Latin script", "SOV", "Non-Scheduled", 0, None, 35000, 2001, ETHNOLOGUE, "Arunachal Pradesh (Lohit, Anjaw)", "Not an official state language", "Vulnerable", None),
    ("Miju Mishmi (Kaman)", "Kaman", None, "mxj", "Sino-Tibetan", "Tibeto-Burman (Mishmi)", "Latin script", "SOV", "Non-Scheduled", 0, None, 18000, 2006, ETHNOLOGUE, "Arunachal Pradesh (Anjaw, Lohit)", "Not an official state language", "Vulnerable", None),
    ("Wancho", "Wancho", None, "nnp", "Sino-Tibetan", "Tibeto-Burman (Konyak-Naga)", "Latin script", "SOV", "Non-Scheduled", 0, None, 59154, 2011, CENSUS, "Arunachal Pradesh (Longding, Tirap)", "Not an official state language", None, None),
    ("Nocte", "Nocte", None, "njb", "Sino-Tibetan", "Tibeto-Burman (Konyak-Naga)", "Latin script", "SOV", "Non-Scheduled", 0, None, 33000, 2001, ETHNOLOGUE, "Arunachal Pradesh (Tirap)", "Not an official state language", None, None),
    ("Tangsa", "Tangsa", None, "nst", "Sino-Tibetan", "Tibeto-Burman (Konyak-Naga)", "Latin script", "SOV", "Non-Scheduled", 0, None, 110000, None, ETHNOLOGUE, "Arunachal Pradesh (Changlang), Assam", "Not an official state language", None, "A dialect cluster of 30+ named varieties; some (e.g. Kyan-Karyaw, Lao Naga) carry separate ISO codes."),
    ("Singpho", "Singpho", None, "sgp", "Sino-Tibetan", "Tibeto-Burman (Jingpho-Luic)", "Latin script", "SOV", "Non-Scheduled", 0, None, 7300, 2011, CENSUS, "Arunachal Pradesh (Changlang), Assam", "Not an official state language", "Endangered", "Indian branch of the Jingpho (Kachin) people spanning Myanmar and China."),
    ("Khamti", "Khamti", None, "kht", "Tai-Kadai", "Southwestern Tai", "Tai Le / Burmese-derived Lik-Tai script", "SVO", "Non-Scheduled", 0, None, 13000, None, ETHNOLOGUE, "Arunachal Pradesh (Namsai, Changlang)", "Not an official state language", "Vulnerable", "A Tai (not Sino-Tibetan) language, one of several Tai/Shan-related languages of eastern Arunachal Pradesh and Assam."),
    # -- Bodo-Koch and other Northeast (Sino-Tibetan) --
    ("Rabha", "Rabha", None, "rah", "Sino-Tibetan", "Tibeto-Burman (Bodo-Koch)", "Latin / Assamese script", "SOV", "Non-Scheduled", 0, None, 139986, 2011, CENSUS, "Assam, West Bengal, Meghalaya", "Not an official state language", None, None),
    ("Tiwa (Lalung)", "Tiwa", None, "lax", "Sino-Tibetan", "Tibeto-Burman (Bodo-Garo)", "Latin script", "SOV", "Non-Scheduled", 0, None, 371000, None, ETHNOLOGUE, "Assam (Morigaon, Karbi Anglong), Meghalaya", "Not an official state language; has an Autonomous Council in Assam", "Vulnerable", None),
    ("Koch", "Koch", None, "kdq", "Sino-Tibetan", "Tibeto-Burman (Bodo-Koch)", "Assamese / Bengali / Latin script", "SOV", "Non-Scheduled", 0, None, 36434, 2011, CENSUS, "Assam, Meghalaya", "Not an official state language", "Definitely Endangered", None),
    ("Deori", "Deori", None, "der", "Sino-Tibetan", "Tibeto-Burman (Bodo-Garo)", "Latin / Assamese script", "SOV", "Non-Scheduled", 0, None, 41000, None, ETHNOLOGUE, "Assam (Brahmaputra Valley), Arunachal Pradesh", "Not an official state language", "Vulnerable", None),
    ("Hrangkhol", "Hrangkhol", None, "hra", "Sino-Tibetan", "Tibeto-Burman (Kuki-Chin, Halam group)", "Latin script", "SOV", "Non-Scheduled", 0, None, 10000, None, ETHNOLOGUE, "Assam (Cachar), Tripura", "Not an official state language", "Vulnerable", None),
    ("Biate", "Biate", None, "bhz", "Sino-Tibetan", "Tibeto-Burman (Kuki-Chin, Halam group)", "Latin script", "SOV", "Non-Scheduled", 0, None, 27000, None, ETHNOLOGUE, "Assam, Mizoram, Meghalaya", "Not an official state language", "Vulnerable", None),
    ("Riang", "Riang", None, "ria", "Sino-Tibetan", "Tibeto-Burman (Bodo-Koch)", "Bengali / Latin script", "SOV", "Non-Scheduled", 0, None, 190000, None, ETHNOLOGUE, "Tripura", "Not an official state language", "Vulnerable", "Distinct from the related but separate Bru/Reang (Kaubru) community of the Tripura-Mizoram border."),
    ("Darlong", "Darlong", None, None, "Sino-Tibetan", "Tibeto-Burman (Kuki-Chin, Halam group)", "Latin script", "SOV", "Non-Scheduled", 0, None, 10000, None, ETHNOLOGUE, "Tripura", "Not an official state language", "Vulnerable", "One of the constituent Halam/Kuki communities of Tripura; not separately assigned an ISO 639-3 code by SIL."),
    # -- Tibetic (Sino-Tibetan) --
    ("Spiti (Spiti Bhoti)", "Spiti", None, "spt", "Sino-Tibetan", "Tibeto-Burman (Tibetic)", "Tibetan script", "SOV", "Non-Scheduled", 0, None, 10000, 2000, ETHNOLOGUE, "Himachal Pradesh (Spiti Valley)", "Not an official state language", "Endangered", None),
    ("Zangskari", "Zangskari", None, "zau", "Sino-Tibetan", "Tibeto-Burman (Tibetic)", "Tibetan script", "SOV", "Non-Scheduled", 0, None, 12000, 2000, ETHNOLOGUE, "Ladakh (Zanskar, Kargil), Himachal Pradesh (Lahaul)", "Not an official Union Territory language", "Endangered", None),
    ("Sherpa", "Sherpa", None, "xsr", "Sino-Tibetan", "Tibeto-Burman (Tibetic)", "Tibetan / Devanagari script", "SOV", "Non-Scheduled", 0, None, 140000, 2011, ETHNOLOGUE, "Sikkim, West Bengal (Darjeeling); chiefly Nepal", "Recognised regional language of Sikkim", "Vulnerable", "Figure is the combined Nepal+India Ethnologue total; the Sikkim/Darjeeling community is a smaller fraction of this."),
    ("Tamang", "Tamang", None, "taj", "Sino-Tibetan", "Tibeto-Burman (Tamangic)", "Tibetan / Devanagari script", "SOV", "Non-Scheduled", 0, None, 250000, None, ETHNOLOGUE, "Sikkim, West Bengal (Darjeeling)", "Recognised regional language of Sikkim", "Vulnerable", "Figure is an Ethnologue-style estimate for the India (Sikkim/Darjeeling) Tamang-speaking community; the wider Tamang dialect cluster (Eastern/Western Tamang etc.) is chiefly spoken in Nepal."),
    ("Gurung", "Gurung", None, "gvr", "Sino-Tibetan", "Tibeto-Burman (Tamangic)", "Devanagari / Tibetan script", "SOV", "Non-Scheduled", 0, None, 380000, 2021, ETHNOLOGUE, "Sikkim; chiefly Nepal", "Official language of Sikkim", "Vulnerable", "Figure is the combined Nepal+India total; Gurung has official-language status in Sikkim but the India-resident community is a small fraction of this total."),
    # -- Munda (Austroasiatic) --
    ("Bhumij", "Bhumij", None, None, "Austroasiatic", "Munda (Kherwarian)", "Devanagari / Ol Chiki", "SOV", "Non-Scheduled", 0, None, 200000, None, ETHNOLOGUE, "Jharkhand, Odisha, West Bengal, Assam", "Not an official state language", "Vulnerable", "Treated by SIL/Ethnologue as covered under the Mundari (unr) code rather than given its own ISO 639-3 code."),
    ("Birhor", "Birhor", None, "biy", "Austroasiatic", "Munda (Kherwarian)", "Devanagari script", "SOV", "Non-Scheduled", 0, None, 2000, None, ETHNOLOGUE, "Jharkhand, Odisha, West Bengal, Chhattisgarh", "Recognised as a Particularly Vulnerable Tribal Group language", "Critically Endangered", "Spoken by one of India's semi-nomadic Particularly Vulnerable Tribal Groups."),
    ("Asur", "Asuri", None, "asr", "Austroasiatic", "Munda (Kherwarian)", "Devanagari script", "SOV", "Non-Scheduled", 0, None, 7500, None, ETHNOLOGUE, "Jharkhand (Netarhat plateau)", "Recognised as a Particularly Vulnerable Tribal Group language", "Endangered", None),
    ("Turi", "Turi", None, "trd", "Austroasiatic", "Munda (Kherwarian)", "Devanagari script", "SOV", "Non-Scheduled", 0, None, 5000, None, ETHNOLOGUE, "Jharkhand, Chhattisgarh", "Not an official state language", "Severely Endangered", None),
    ("Bonda (Remo)", "Remo", None, "bfw", "Austroasiatic", "Munda (South Munda)", "Odia script", "SOV", "Non-Scheduled", 0, None, 9000, None, ETHNOLOGUE, "Odisha (Malkangiri)", "Recognised as a Particularly Vulnerable Tribal Group language", "Severely Endangered", None),
    ("Gorum (Parenga)", "Parengi", None, "pcj", "Austroasiatic", "Munda (South Munda)", "Odia script", "SOV", "Non-Scheduled", 0, None, 1500, None, ETHNOLOGUE, "Odisha (Koraput)", "Not an official state language", "Critically Endangered", "Described in the linguistic literature as a near-extinct minor Munda language."),
    ("Gutob (Gadaba)", "Gutob", None, "gbj", "Austroasiatic", "Munda (South Munda)", "Odia script", "SOV", "Non-Scheduled", 0, None, 40000, None, ETHNOLOGUE, "Odisha (Koraput), Andhra Pradesh", "Not an official state language", "Vulnerable", "Not to be confused with the unrelated Dravidian-speaking Gadaba (Ollari/Kondekor) communities of the same region."),
    # -- Minor Dravidian --
    ("Parji", "Parji", None, "pci", "Dravidian", "Central Dravidian", "Devanagari script", "SOV", "Non-Scheduled", 0, None, 8000, None, ETHNOLOGUE, "Chhattisgarh (Bastar), Odisha", "Not an official state language", "Endangered", None),
    ("Ollari Gadaba", "Ollari", None, "gdb", "Dravidian", "South-Central Dravidian", "Odia script", "SOV", "Non-Scheduled", 0, None, 5000, None, ETHNOLOGUE, "Odisha, Andhra Pradesh (Koraput/border)", "Not an official state language", "Severely Endangered", None),
    ("Kondekor Gadaba", "Kondekor", None, "gau", "Dravidian", "South-Central Dravidian", "Telugu / Odia script", "SOV", "Non-Scheduled", 0, None, 3000, None, ETHNOLOGUE, "Andhra Pradesh, Odisha border", "Not an official state language", "Severely Endangered", "Distinct Dravidian-speaking Gadaba community from the Austroasiatic Gutob-speaking Gadaba."),
    ("Manda", "Manda", None, "mha", "Dravidian", "South-Central Dravidian", "Odia script", "SOV", "Non-Scheduled", 0, None, 5000, None, ETHNOLOGUE, "Odisha (Koraput)", "Not an official state language", "Severely Endangered", None),
    ("Pengo", "Pengo", None, "peg", "Dravidian", "South-Central Dravidian", "Odia script", "SOV", "Non-Scheduled", 0, None, 4000, None, ETHNOLOGUE, "Odisha (Koraput)", "Not an official state language", "Severely Endangered", None),
    ("Naiki", "Naiki", None, "nit", "Dravidian", "Central Dravidian", "Devanagari script", "SOV", "Non-Scheduled", 0, None, 9000, None, ETHNOLOGUE, "Maharashtra, Telangana", "Not an official state language", "Endangered", "Southeastern branch of the Kolami-Naiki dialect continuum."),
    ("Kurumba", "Kurumba", None, "kfi", "Dravidian", "Southern Dravidian", "Tamil / Kannada script", "SOV", "Non-Scheduled", 0, None, 2000, None, ETHNOLOGUE, "Tamil Nadu, Karnataka, Kerala (Nilgiris)", "Not an official state language", "Severely Endangered", "One of several closely related but distinct Kurumba varieties (Betta, Jenu, Alu, Mullu Kurumba) of the Nilgiri hills."),
    ("Betta Kurumba", "Betta Kurumba", None, "xub", "Dravidian", "Southern Dravidian", "Tamil / Kannada script", "SOV", "Non-Scheduled", 0, None, 32000, None, ETHNOLOGUE, "Tamil Nadu, Karnataka, Kerala (Nilgiris)", "Not an official state language", "Vulnerable", None),
    ("Jenu Kurumba", "Jenu Kurumba", None, "xuj", "Dravidian", "Southern Dravidian", "Kannada / Tamil script", "SOV", "Non-Scheduled", 0, None, 100000, 2011, ETHNOLOGUE, "Karnataka, Tamil Nadu, Kerala (Nilgiris/Wayanad)", "Not an official state language", "Vulnerable", None),
    ("Koraga", "Koraga", None, "kfd", "Dravidian", "Southern Dravidian", "Kannada script", "SOV", "Non-Scheduled", 0, None, 7000, None, ETHNOLOGUE, "Karnataka, Kerala (coastal)", "Recognised as a Particularly Vulnerable Tribal Group language", "Severely Endangered", None),
    ("Paniya", "Paniya", None, "pcg", "Dravidian", "Southern Dravidian", "Malayalam / Kannada script", "SOV", "Non-Scheduled", 0, None, 140000, None, ETHNOLOGUE, "Kerala (Wayanad), Karnataka, Tamil Nadu", "Not an official state language", "Vulnerable", "One of the largest Adivasi-language communities of the Wayanad/Nilgiris region."),
    ("Muthuvan", "Muthuvan", None, "muv", "Dravidian", "Southern Dravidian", "Malayalam script", "SOV", "Non-Scheduled", 0, None, 28000, None, ETHNOLOGUE, "Kerala, Tamil Nadu (Western Ghats)", "Not an official state language", "Vulnerable", None),
    # -- Himalayan / hill Indo-Aryan (Pahari and related) --
    ("Ahirani", "अहिराणी", None, "ahr", "Indo-European", "Indo-Aryan (Southern, Marathi-related)", "Devanagari script", "SOV", "Non-Scheduled", 0, None, 4600000, None, ETHNOLOGUE, "Maharashtra (Khandesh: Nashik, Dhule, Jalgaon)", "Not an official state language", None, None),
    ("Varhadi", "वऱ्हाडी", None, None, "Indo-European", "Indo-Aryan (Southern, Marathi dialect)", "Devanagari script", "SOV", "Non-Scheduled", 0, None, 7000000, None, ETHNOLOGUE, "Maharashtra (Vidarbha region)", "Not an official state language", None, "Regarded linguistically as a major dialect of Marathi rather than a separately ISO-coded language; not separately tabulated in the census."),
    ("Powari", "पवारी", None, "pwr", "Indo-European", "Indo-Aryan (Southern, Marathi-related)", "Devanagari script", "SOV", "Non-Scheduled", 0, None, 1000000, None, ETHNOLOGUE, "Madhya Pradesh, Maharashtra, Chhattisgarh border", "Not an official state language", "Vulnerable", None),
    ("Bagri", "बागड़ी", None, "bgq", "Indo-European", "Indo-Aryan (Western, Rajasthani)", "Devanagari script", "SOV", "Non-Scheduled", 0, None, 2500000, None, ETHNOLOGUE, "Rajasthan (Bikaner/Ganganagar), Haryana, Punjab", "Not an official state language", None, None),
    ("Gojri (Gujari)", "गोजरी", None, "gju", "Indo-European", "Indo-Aryan (Western, Rajasthani-related)", "Perso-Arabic / Devanagari", "SOV", "Non-Scheduled", 0, None, 1200000, None, ETHNOLOGUE, "Jammu & Kashmir, Himachal Pradesh, Uttarakhand", "Not an official state language", "Vulnerable", "Language of the transhumant Gujjar pastoralist community across the western Himalaya."),
    ("Kangri", "कांगड़ी", None, "xnr", "Indo-European", "Indo-Aryan (Western Pahari)", "Devanagari script", "SOV", "Non-Scheduled", 0, None, 1300000, None, ETHNOLOGUE, "Himachal Pradesh (Kangra Valley)", "Not an official state language", None, None),
    ("Chambeali", "चंबियाली", None, "cdh", "Indo-European", "Indo-Aryan (Western Pahari)", "Devanagari / Takri script", "SOV", "Non-Scheduled", 0, None, 130000, None, ETHNOLOGUE, "Himachal Pradesh (Chamba)", "Not an official state language", "Vulnerable", None),
    ("Mandeali", "मंडियाली", None, "mjl", "Indo-European", "Indo-Aryan (Western Pahari)", "Devanagari script", "SOV", "Non-Scheduled", 0, None, 600000, None, ETHNOLOGUE, "Himachal Pradesh (Mandi)", "Not an official state language", None, None),
    ("Sirmauri", "सिरमौरी", None, "srx", "Indo-European", "Indo-Aryan (Western Pahari)", "Devanagari script", "SOV", "Non-Scheduled", 0, None, 100000, None, ETHNOLOGUE, "Himachal Pradesh (Sirmaur)", "Not an official state language", "Vulnerable", None),
    ("Jaunsari", "जौनसारी", None, "jns", "Indo-European", "Indo-Aryan (Western Pahari)", "Devanagari script", "SOV", "Non-Scheduled", 0, None, 100000, None, ETHNOLOGUE, "Uttarakhand (Jaunsar-Bawar), Himachal Pradesh", "Not an official state language", "Vulnerable", None),
    ("Gaddi", "गद्दी", None, "gbk", "Indo-European", "Indo-Aryan (Western Pahari)", "Devanagari / Takri script", "SOV", "Non-Scheduled", 0, None, 130000, None, ETHNOLOGUE, "Himachal Pradesh (Bharmour/Chamba), Jammu & Kashmir", "Not an official state language", "Vulnerable", "Language of the transhumant pastoralist Gaddi community of the Dhauladhar range."),
    ("Pangwali", "पांगवाली", None, "pgg", "Indo-European", "Indo-Aryan (Western Pahari)", "Devanagari / Takri script", "SOV", "Non-Scheduled", 0, None, 20000, None, ETHNOLOGUE, "Himachal Pradesh (Pangi valley, Chamba)", "Not an official state language", "Endangered", None),
    ("Bhadrawahi", "भद्रवाही", None, "bhd", "Indo-European", "Indo-Aryan (Western Pahari)", "Devanagari / Takri script", "SOV", "Non-Scheduled", 0, None, 50000, None, ETHNOLOGUE, "Jammu & Kashmir (Bhaderwah), Himachal Pradesh", "Not an official state language", "Vulnerable", None),
    ("Kishtwari", "किश्तवाड़ी", None, "kis", "Indo-European", "Indo-Aryan (Dardic-Kashmiri related)", "Perso-Arabic / Devanagari", "SOV", "Non-Scheduled", 0, None, 100000, None, ETHNOLOGUE, "Jammu & Kashmir (Kishtwar)", "Not an official Union Territory language", "Vulnerable", None),
    ("Deccani (Dakhini)", "दक्खिनी / دکنی", None, "dcc", "Indo-European", "Indo-Aryan (Central, Urdu-related)", "Perso-Arabic (Nastaliq)", "SOV", "Non-Scheduled", 0, None, 10000000, None, ETHNOLOGUE, "Telangana (Hyderabad), Karnataka, Tamil Nadu, Maharashtra", "Usually counted under Urdu/Hindi in the census, not separately tabulated", None, "Koine that developed in the Deccan Sultanates; today the everyday spoken register of Hyderabad and other south Indian Muslim communities."),
    ("Saurashtra", "सौराष्ट्र / ꢱꣃꢬꢵꢰ꣄ꢜ꣄ꢬ", None, "saz", "Indo-European", "Indo-Aryan (Southern)", "Saurashtra script / Tamil / Devanagari", "SOV", "Non-Scheduled", 0, None, 190000, None, ETHNOLOGUE, "Tamil Nadu (Madurai, Salem, Thanjavur)", "Not an official state language", "Vulnerable", "Spoken by the Saurashtrian silk-weaving community, descended from Gujarat migrants settled in Tamil Nadu since the medieval period."),
    # -- Indo-Aryan tribal (Bhil-adjacent, western India) --
    ("Wagdi", "वागड़ी", None, "wbr", "Indo-European", "Indo-Aryan (Bhil)", "Devanagari script", "SOV", "Non-Scheduled", 0, None, 1100000, None, ETHNOLOGUE, "Rajasthan (Dungarpur, Banswara)", "Not an official state language", None, None),
    ("Vasavi", "वसावी", None, "vas", "Indo-European", "Indo-Aryan (Bhil)", "Devanagari script", "SOV", "Non-Scheduled", 0, None, 187000, 2011, CENSUS, "Gujarat (Bharuch), Maharashtra (Dhule)", "Not an official state language", "Vulnerable", None),
    ("Kokni (Kokna)", "कोकणी", None, None, "Indo-European", "Indo-Aryan (Bhil)", "Devanagari script", "SOV", "Non-Scheduled", 0, None, 180000, None, ETHNOLOGUE, "Maharashtra, Gujarat, Dadra & Nagar Haveli", "Not an official state language", "Vulnerable", "A Bhil tribal language of the Sahyadri hill belt, distinct from the unrelated Indo-Aryan Konkani language of Goa despite the similar name."),
    ("Warli", "वारली", None, "vav", "Indo-European", "Indo-Aryan (Bhil)", "Devanagari script", "SOV", "Non-Scheduled", 0, None, 390000, 2011, CENSUS, "Maharashtra, Gujarat, Dadra & Nagar Haveli", "Not an official state language", "Vulnerable", "Spoken by the Warli community, known for their distinctive Warli folk-art tradition."),
    ("Katkari", "कातकरी", None, "kfu", "Indo-European", "Indo-Aryan (Southern, Marathi-related)", "Devanagari script", "SOV", "Non-Scheduled", 0, None, 12000, 2007, ETHNOLOGUE, "Maharashtra (Konkan/Thane region)", "Recognised as a Particularly Vulnerable Tribal Group language", "Vulnerable", None),
    # -- Great Andamanese (mostly extinct pre-contact varieties) and Nicobarese --
    ("Aka-Bo", "Aka-Bo", None, "akm", "Great Andamanese", "Great Andamanese (Northern)", "Unwritten / no standard script", "SOV", "Non-Scheduled", 0, None, 0, None, ETHNOLOGUE, "North Andaman Island (historical)", "Extinct; no state or territory recognition", "Extinct", "Became extinct on 26 January 2010 with the death of its last speaker, Boa Sr, ending an Andamanese language lineage estimated at 65,000+ years old."),
    ("Aka-Jeru", "Aka-Jeru", None, "akj", "Great Andamanese", "Great Andamanese (Northern)", "Unwritten / no standard script", "SOV", "Non-Scheduled", 0, None, 3, 2020, ETHNOLOGUE, "Strait Island, Andaman Islands", "Not an official territory language", "Critically Endangered", "The last surviving distinct Great Andamanese variety; its remaining speakers largely use the composite 'Present Great Andamanese' (gac) day to day."),
    ("Aka-Cari", "Akachari", None, "aci", "Great Andamanese", "Great Andamanese (Northern)", "Unwritten / no standard script", "SOV", "Non-Scheduled", 0, None, 0, None, ETHNOLOGUE, "North Andaman Island (historical)", "Extinct; no state or territory recognition", "Extinct", "Became extinct on 4 April 2020 with the death of its last speaker, Licho."),
    ("Aka-Kora", "Akakhora", None, "ack", "Great Andamanese", "Great Andamanese (Northern)", "Unwritten / no standard script", "SOV", "Non-Scheduled", 0, None, 0, None, ETHNOLOGUE, "North Andaman Island (historical)", "Extinct; no state or territory recognition", "Extinct", "Became extinct in November 2009 with the death of its last speaker, Boro."),
    ("Oko-Juwoi", "Oko-Juwoi", None, "okj", "Great Andamanese", "Great Andamanese (Central)", "Unwritten / no standard script", "SOV", "Non-Scheduled", 0, None, 0, None, ETHNOLOGUE, "Middle Andaman Island (historical)", "Extinct; no state or territory recognition", "Extinct", "The Juwoi people were already extinct as a distinct community by 1931."),
    ("Nancowry", "Nancowry", None, None, "Austroasiatic", "Nicobarese (Central)", "Latin script", "SVO", "Non-Scheduled", 0, None, 930, 2001, CENSUS, "Nancowry Island, Camorta, Katchal (Central Nicobars)", "Not an official territory language", "Vulnerable", "Central Nicobarese variety; not separately assigned an ISO 639-3 code by SIL, which groups the Central Nicobarese continuum together."),
    # -- Language isolate --
    ("Nihali", "निहाली", None, "nll", "Language isolate", "Unclassified (possible pre-Munda/pre-Dravidian substrate)", "Devanagari script", "SOV", "Non-Scheduled", 0, None, 2500, 2016, ETHNOLOGUE, "Maharashtra (Jalgaon Jamod, Buldhana), Madhya Pradesh border", "Not an official state language", "Critically Endangered", "India's only confirmed language isolate; despite heavy lexical borrowing from Korku, Marathi and Hindi, its core vocabulary and grammar cannot be linked to any known language family."),
]

LANGUAGES.extend(LANGUAGES_BATCH_2)


def build_reference_tables(conn):
    conn.execute("""
        CREATE TABLE language_families (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT
        )
    """)
    conn.executemany("INSERT INTO language_families (name, description) VALUES (?, ?)", FAMILIES)

    conn.execute("""
        CREATE TABLE writing_systems (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            type TEXT,
            description TEXT
        )
    """)
    conn.executemany("INSERT INTO writing_systems (name, type, description) VALUES (?, ?, ?)", SCRIPTS)


def build_languages_table(conn):
    conn.execute("""
        CREATE TABLE languages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            native_name TEXT,
            iso_639_1 TEXT,
            iso_639_3 TEXT,
            family TEXT NOT NULL,
            branch TEXT,
            script TEXT,
            word_order TEXT,
            classification TEXT NOT NULL,
            is_classical INTEGER NOT NULL DEFAULT 0,
            classical_since INTEGER,
            speakers_approx INTEGER,
            census_year INTEGER,
            source TEXT,
            primary_regions TEXT,
            status TEXT,
            endangerment TEXT,
            notes TEXT
        )
    """)
    conn.executemany(
        """INSERT INTO languages
           (name, native_name, iso_639_1, iso_639_3, family, branch, script, word_order,
            classification, is_classical, classical_since, speakers_approx, census_year,
            source, primary_regions, status, endangerment, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        LANGUAGES,
    )
    conn.execute("CREATE INDEX idx_languages_family ON languages(family)")
    conn.execute("CREATE INDEX idx_languages_name ON languages(name)")


def main():
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    build_reference_tables(conn)
    build_languages_table(conn)
    conn.commit()
    conn.close()
    print(f"languages: {len(LANGUAGES)} rows -> {DB_PATH}")
    print(f"language_families: {len(FAMILIES)} rows")
    print(f"writing_systems: {len(SCRIPTS)} rows")


if __name__ == "__main__":
    main()
