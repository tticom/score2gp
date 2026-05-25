import zipfile

def main():
    try:
        with zipfile.ZipFile('fixtures/private/Derek Trucks BB King.gp') as z:
            xml_content = z.read('Content/score.gpif').decode('utf-8')
            
            for keyword in ['anacrusis', 'barline', 'repeat', 'double', 'end']:
                print(f"Occurrences of '{keyword}':")
                idx = 0
                count = 0
                while True:
                    idx = xml_content.lower().find(keyword, idx)
                    if idx == -1:
                        break
                    count += 1
                    snippet = xml_content[max(0, idx - 50):min(len(xml_content), idx + 100)]
                    print(f"  [{count}] At index {idx}: ... {snippet.strip().replace('\n', ' ')} ...")
                    idx += len(keyword)
                if count == 0:
                    print("  None")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    main()
