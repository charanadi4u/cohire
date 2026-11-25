"""Offline release report. Never mutates live model, prompt or rubric configuration."""
import json, argparse
from pathlib import Path

def evaluate(rows):
    seen=set();counts={'correct':0,'total':0}
    for row in rows:
        key=(row['candidate_id'],row['job_id'])
        if key in seen:raise ValueError('Duplicate candidate/job across evaluation rows')
        seen.add(key)
        if row['split']!='test':raise ValueError('Only frozen held-out test rows accepted')
        counts['total']+=1;counts['correct']+=row['predicted']==row['expected']
    return {**counts,'accuracy':counts['correct']/counts['total'] if counts['total'] else None,
            'promotion':'requires_accountable_release_review','limitations':['Synthetic accuracy is not hiring validity.','Unseen/unreviewed candidates are not negative labels.','No automatic learning or weight changes.']}
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('input');args=parser.parse_args()
    print(json.dumps(evaluate(json.loads(Path(args.input).read_text())),indent=2))
