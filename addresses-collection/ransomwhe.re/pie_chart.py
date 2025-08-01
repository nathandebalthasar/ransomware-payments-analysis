"""
Generate a pie chart to show the distribution of ransomware families.
"""

import matplotlib.pyplot as plt
import json

def generate_pie_chart(attributes, values, title="Pie Chart", threshold=5):
    total = sum(values)
    filtered_attributes = []
    filtered_values = []
    others_value = 0

    for attr, val in zip(attributes, values):
        percent = (val / total) * 100
        if percent < threshold:
            others_value += val
        else:
            filtered_attributes.append(attr)
            filtered_values.append(val)

    if others_value > 0:
        filtered_attributes.append("Others")
        filtered_values.append(others_value)

    plt.figure(figsize=(8, 8))
    wedges, texts, autotexts = plt.pie(
        filtered_values,
        labels=filtered_attributes,
        autopct='%1.1f%%',
        startangle=90,
        pctdistance=0.8,
        labeldistance=1.1
    )

    for text in texts:
        text.set_fontsize(10)
    for autotext in autotexts:
        autotext.set_fontsize(9)

    plt.title(title)
    plt.axis('equal')

    plt.legend(wedges, filtered_attributes, title="Families", loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))

    plt.tight_layout()
    plt.show()

with open('./data.json', 'r') as f:
    data = json.load(f)

all_families = [item['family'] for item in data]
unique_families = list(set(all_families))
values = [all_families.count(family) for family in unique_families]

generate_pie_chart(unique_families, values, title="Ransomware Family Distribution", threshold=5)
