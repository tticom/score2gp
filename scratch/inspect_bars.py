import json

def main():
    path = 'work/private_e2e_smoke_v0_1/private_input_custom_lesson_3/score.ir.json'
    with open(path, 'r') as f:
        data = json.load(f)
        
    print(f"Schema Version: {data.get('schema_version')}")
    print(f"Title: {data.get('metadata', {}).get('title')}")
    
    bars = data.get('bars', [])
    print(f"Total Bars in IR: {len(bars)}")
    
    for idx, bar in enumerate(bars[:5]):
        events = bar.get('events', [])
        print(f"  Bar {idx}: events count = {len(events)}")
        for e_idx, e in enumerate(events):
            notes = e.get('notes', [])
            onset = e.get('timing', {}).get('onset_ticks')
            duration = e.get('timing', {}).get('duration_ticks')
            voice = e.get('timing', {}).get('voice')
            print(f"    Event {e_idx}: onset={onset}, duration={duration}, voice={voice}, notes={notes}")

if __name__ == '__main__':
    main()
