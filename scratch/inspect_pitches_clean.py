import json

def main():
    path = 'work/private_e2e_smoke_v0_1/private_input_custom_lesson_3/score.ir.json'
    with open(path, 'r') as f:
        data = json.load(f)
        
    bars = data.get('bars', [])
    bar0 = bars[0]
    events = bar0.get('events', [])
    
    print("=== BAR 0 EVENTS ===")
    for e in events:
        onset = e.get('timing', {}).get('onset_ticks')
        voice = e.get('timing', {}).get('voice')
        notes = []
        for n in e.get('notes', []):
            notes.append(f"string={n.get('string')}, fret={n.get('fret')}, pitch={n.get('pitch')}")
        print(f"Voice {voice} at onset {onset}: {notes}")

if __name__ == '__main__':
    main()
