"""Fixed name lists for generated merchants (SPEC §5.5).

Common Mumbai first names (English, Devanagari) and surnames. "Anil", "Ramesh" and "Sunil" are
deliberately absent so no generated shop can be confused with the demo merchants or with the
mismatch-slip patient "Sunil Pawar" (SPEC §5.4, §17.2).
"""

from __future__ import annotations

FIRST_NAMES: tuple[tuple[str, str], ...] = (
    ("Santosh", "संतोष"), ("Vijay", "विजय"), ("Prakash", "प्रकाश"), ("Ganesh", "गणेश"),
    ("Mahesh", "महेश"), ("Suresh", "सुरेश"), ("Rajesh", "राजेश"), ("Dinesh", "दिनेश"),
    ("Sachin", "सचिन"), ("Rahul", "राहुल"), ("Amit", "अमित"), ("Sandeep", "संदीप"),
    ("Manoj", "मनोज"), ("Ashok", "अशोक"), ("Vinod", "विनोद"), ("Deepak", "दीपक"),
    ("Nitin", "नितिन"), ("Anand", "आनंद"), ("Sanjay", "संजय"), ("Ravi", "रवि"),
    ("Kiran", "किरण"), ("Pravin", "प्रवीण"), ("Mangesh", "मंगेश"), ("Nilesh", "निलेश"),
    ("Umesh", "उमेश"), ("Prashant", "प्रशांत"), ("Rupesh", "रूपेश"), ("Yogesh", "योगेश"),
    ("Imran", "इमरान"), ("Salim", "सलीम"), ("Asif", "आसिफ"), ("Farhan", "फरहान"),
    ("Joseph", "जोसेफ"), ("Sunita", "सुनीता"), ("Lata", "लता"), ("Meena", "मीना"),
    ("Rekha", "रेखा"), ("Asha", "आशा"), ("Savita", "सविता"), ("Kavita", "कविता"),
    ("Pooja", "पूजा"), ("Shabana", "शबाना"),
)  # fmt: skip

# Middle names on KYC records are the father's first name (as in "ANIL RAMESH JADHAV").
FATHER_NAMES: tuple[str, ...] = (
    "Vasant", "Shankar", "Dattatray", "Maruti", "Narayan", "Bhaskar", "Sitaram", "Ramchandra",
    "Hanumant", "Dnyaneshwar", "Yusuf", "Abdul", "Francis", "Gopal", "Mohan", "Balkrishna",
)  # fmt: skip

SURNAMES: tuple[str, ...] = (
    "Patil", "Jadhav", "Shinde", "More", "Gaikwad", "Kadam", "Chavan", "Salunkhe",
    "Deshmukh", "Kamble", "Sawant", "Naik", "Shaikh", "Khan", "Ansari", "Gupta",
    "Yadav", "Mishra", "Singh", "D'Souza", "Fernandes", "Shetty", "Rao", "Bhosale",
)  # fmt: skip
