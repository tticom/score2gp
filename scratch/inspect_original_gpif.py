import zipfile

original_gp_path = "fixtures/private/Lesson-3.gp"
with zipfile.ZipFile(original_gp_path, 'r') as zip_ref:
    gpif_content = zip_ref.read("Content/score.gpif").decode('utf-8')

with open("scratch/original_lesson_3.gpif", "w", encoding="utf-8") as f:
    f.write(gpif_content)

print("Extracted original. Length:", len(gpif_content))
