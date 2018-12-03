from argparse import ArgumentParser
from collections import defaultdict
from functools import partial
from itertools import chain
import logging

import numpy as np
import os
import pandas
import re

parser = ArgumentParser(description='This script extracts document meta data from the RUEG questionnaire results'
                                    ' and processes it to .meta files.')
parser.add_argument('survey_results_file', type=str, help='path to survey answers file (csv)')
parser.add_argument('target_dir', type=str, help='output directory for .meta-files')
parser.add_argument('-d', action='store_true', help='activate debug logging')
parser.add_argument('-r', action='store_true', help='activate relaxed mode (codes don\'t have to match code pattern)')
args = parser.parse_args()

log_level = logging.DEBUG if args.d else logging.INFO
logging.basicConfig(level=log_level)
logger = logging.getLogger(__name__)

raw_data = pandas.read_table(args.survey_results_file, sep=',')
raw_data['datestamp'] = pandas.to_datetime(raw_data['datestamp'])
raw_data['dateofbirth'] = pandas.to_datetime(raw_data['dateofbirth'])


CODE_PATTERN = r'(D[Ee]|U[Ss]|R[Uu]|G[Rr]|T[Rr])(bi|mo)[0-9][0-9](M|F)(R|G|D|E|T)'


def value(data_frame, column_name, astype=None, transform=lambda x: x):
    values = data_frame[column_name]
    if astype is not None:
        values = values.astype(astype)
    return transform(values)


def cs_values(data_frame, column_names, transform=lambda e: e):
    data = []
    for name in column_names:
        data.append(data_frame[name])
    ret_val = []
    for line in np.array(data).T:
        ret_val.append(', '.join(np.unique([transform(e).strip() for e in line if not pandas.isnull(e)])))
    return ret_val


def age(data_frame, timestamp_name='datestamp', dateofbirth_name='dateofbirth'):
    timestamp = np.array((data_frame[timestamp_name].dt.year, data_frame[timestamp_name].dt.month)).T
    dateofbirth = np.array((data_frame[dateofbirth_name].dt.year, data_frame[dateofbirth_name].dt.month)).T
    float_age = (timestamp - dateofbirth).clip(min=(0, -1), max=(200, 0)).sum(axis=1)
    return np.nan_to_num(float_age).astype(np.int)


def age_group(data_frame):
    '''
    This is a heuristic to determine which age group the parcipant data belongs to. 
    We assume that the questionnaire for children / adolescent does not contain question id "jobstatus".
    There are other and maybe better ways ...
    '''
    if 'jobstatus' in data_frame.columns:
        name = 'adult'
    else:
        name = 'child/adolescent'
    return [name] * len(data_frame)


def bilingual_status(data_frame, heritage_lang_column_name='languagesmh[LHER_LCHN]'):
    return data_frame[heritage_lang_column_name].apply(pandas.notnull)


def idle(_df):
    return [''] * len(_df)


personality_criteria = {'extraversion': ('character[CH1]', 'character[CH6]'),
                        'aggreeableness': ('character[CH2]', 'character[CH7]'),
                        'conscientiousness': ('character[CH3]', 'character[CH8]'),
                        'emotional-stability': ('character[CH4]', 'character[CH9]'),
                        'openness': ('character[CH5]', 'character[CH10]')}
scoring = {
    'Disagree strongly': 1,
    'Disagree moderately': 2,
    'Disagree a little': 3,
    'Neither agree nor disagree': 4,
    np.nan: 4,  # ATTENTION: Strong decision, what to do?
    'Agree a little': 5,
    'Agree moderately': 6,
    'Agree strongly': 7
}


def tipi(data_frame, score_key):
    score_name, reversed_score_name = personality_criteria[score_key]
    scores = data_frame[score_name].map(scoring)
    reversed_scores = data_frame[reversed_score_name].map({k: 8 - v for k, v in scoring.items()})
    mean_scores = np.mean((scores, reversed_scores), axis=0)
    return ['{}/7'.format(int(score) if score.is_integer() else score) for score in mean_scores]


target_to_extractor = {
    'speaker-id': partial(value,
                          column_name='name',
                          transform=partial(pandas.Series.apply,
                                            func=lambda x: str(x).strip() if pandas.notnull(x) else x)),
    'speaker-bilingual': bilingual_status, # bool
    'elicitation-country': partial(value, column_name='countryelicitation'),
    'elicitation-date': partial(value, 
                                column_name='datestamp', 
                                transform=partial(pandas.Series.apply, 
                                                  func=lambda ts: '.'.join((str(ts.day), str(ts.month), str(ts.year))))),
    'speaker-language-s': partial(cs_values, 
                                  column_names=['lmaj', 
                                                'languagesmh[LHERA_LCHN]', 
                                                'languagesmh[LHERA_LCHN]', 
                                                'languages[L31]',
                                                'languages[L32]',
                                                'languages[L33]',
                                                'languages[L34]',
                                                'languages[L35]'],
                                  transform=lambda x: x.strip().title()),
    'speaker-age-group': age_group,
    'speaker-gender': partial(value, column_name='gender'),
    'speaker-age': age,
    'speaker-AoO': partial(value, 
                           column_name='languagesmh[LHERA_LCHT]', 
                           transform=partial(pandas.Series.map, arg=lambda x: x if pandas.notnull(x) else 'n/a')),
    'speaker-personality-score-extraversion': partial(tipi, score_key='extraversion'),
    'speaker-personality-score-aggreeableness': partial(tipi, score_key='aggreeableness'),
    'speaker-personality-score-conscientiousness': partial(tipi, score_key='conscientiousness'),
    'speaker-personality-score-emotional-stability': partial(tipi, score_key='emotional-stability'),
    'speaker-personality-score-openness': partial(tipi, score_key='openness'),
    '_project': partial(value, column_name='projectid')
}

data = pandas.DataFrame()
for file_name, function in target_to_extractor.items():
    data[file_name] = function(raw_data)

out_kv = defaultdict(set)
for code in data['speaker-id']:
    if not pandas.isnull(code) and (args.r or re.match(CODE_PATTERN, code)):
        for file_name in data:
            if not file_name.startswith('_'):
                val = data[data['speaker-id'] == code][file_name]
                out_kv[code].add('='.join((file_name, str(val.values[0]))))
    else:
        logger.warn('Dropped code {}'.format(code))


def name_matches(file_name):
    return '_' in file_name and re.match(CODE_PATTERN, file_name)


all_matching_file_names = filter(name_matches, chain(*(entry[2] for entry in os.walk('.'))))
suffixes_by_code = defaultdict(set)
for file_name in all_matching_file_names:
    code, suffix, _ = re.split(r'_|\.', file_name)
    suffixes_by_code[code].add(suffix)

INVALID_DIGIT = '<INVALID DIGIT>'


def formality_from_suffix(suffix):
    return 'informal' if suffix[0] == 'i' else ('formal' if suffix[0] == 'f' else INVALID_DIGIT)


def mode_from_suffix(suffix):
    return 'spoken' if suffix[1] == 's' else ('written' if suffix[1] == 'w' else INVALID_DIGIT)



_LANG_DIGIT_TO_LANG = {
    'D': 'German',
    'E': 'English',
    'G': 'Greek',
    'R': 'Russian',
    'T': 'Turkish'
}
lang_dict = defaultdict(partial(str, INVALID_DIGIT), _LANG_DIGIT_TO_LANG)


def elicitation_lang_from_suffix(suffix):
    return lang_dict[suffix[2]] if len(suffix) > 2 else INVALID_DIGIT


def additional_meta_data(suffix):
    if len(suffix) < 3:
        logger.warn('File suffix {} is not a valid suffix (code {})'.format(suffix, code))
    empty_value = '<NO VALUE>'
    return [('formality', formality_from_suffix(suffix)),
            ('mode', mode_from_suffix(suffix)),
            ('elicitation-order', empty_value),  # to be taken from additional file
            ('elicitation-language', elicitation_lang_from_suffix(suffix)),  # take from elicitation file name
            ('transcriber-id', empty_value),  # to be added by transcriber
            ('elicitator-id', empty_value)]


if not os.path.exists(args.target_dir):
    os.mkdir(args.target_dir)
for file_code, metadata in out_kv.items():
    for sfx in suffixes_by_code[file_code]:
        with open(os.path.join(args.target_dir, '{}_{}.meta'.format(file_code, sfx)), 'w') as f:
            f.write(os.linesep.join(sorted(metadata) + \
                                    ['='.join((k, v)) for k, v in additional_meta_data(sfx)] + \
                                    ['']))
