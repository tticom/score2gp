import zipfile

def main():
    try:
        with zipfile.ZipFile('fixtures/private/Derek Trucks BB King.gp') as z:
            xml_content = z.read('Content/score.gpif').decode('utf-8').lower()
            
            for keyword in ['anacrusis', 'barline', 'repeat', 'double']:
                count = xml_content.count(keyword)
                print(f"Keyword '{keyword}': found {count} times")
                if count > 0:
                    idx = 0
                    for _ in range(min(5, count)):
                        idx = xml_content.find(keyword, idx)
                        snippet = xml_content[max(0, idx - 40):min(len(xml_content), idx + 80)]
                        print(f"  Snippet: ... {snippet.strip().replace('\n', ' ')} ...")
                        idx += len(keyword)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    main()
