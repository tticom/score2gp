import zipfile
import xml.etree.ElementTree as ET

gp_path = "work/private_e2e_smoke_v0_1/private_input_custom_lesson_3/smoke.gp"
with zipfile.ZipFile(gp_path, 'r') as zip_ref:
    for name in zip_ref.namelist():
        print("Zip member:", name)
    gpif_content = zip_ref.read("Content/score.gpif").decode('utf-8')

# Write to scratch to view
with open("scratch/extracted_score.gpif", "w", encoding="utf-8") as f:
    f.write(gpif_content)

print("Extracted. Length:", len(gpif_content))
