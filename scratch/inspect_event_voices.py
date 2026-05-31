import json

def main():
    path = 'work/private_e2e_smoke_v0_1/private_input_custom_lesson_3/score.ir.json'
    with open(path, 'r') as f:
        data = json.load(f)
        
    bars = data.get('bars', [])
    for idx, bar in enumerate(bars[:5]):
        events = bar.get('events', [])
        voices = [e.get('timing', {}).get('voice') for e in events]
        onsets = [e.get('timing', {}).get('onset_ticks') for e in events]
        print(f"Bar {idx}: events count = {len(events)}")
        print(f"  Voices: {voices}")
        print(f"  Onsets: {onsets}")

if __name__ == '__main__':
    main()
