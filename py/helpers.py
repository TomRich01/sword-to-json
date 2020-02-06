import json
import os
import re

default_encoding = 'utf-8'


def does_bible_json_exist(version, language):
    path = os.path.abspath(f'bibles/{language}/{version}')
    filename = f'{path}/{version}.json'
    npm = f'{path}/{version}.js'
    return {
        'exists': os.path.exists(filename),
        'path': path,
        'filename': filename,
        'npm': npm
    }


def write_bible_json(bible, partials, npm):
    version = bible['version']
    language = bible['meta']['language']
    encoding = bible['meta']['encoding'] or default_encoding
    exists_obj = does_bible_json_exist(version, language)

    # make dir if not exists
    if not os.path.exists(exists_obj['path']):
        os.makedirs(exists_obj['path'])

    if npm:
        print(f'{version} - writing NPM file')
        with open(exists_obj['npm'], 'w', encoding=encoding) as f:
            f.write('var '+version+'='+json.dumps(bible, ensure_ascii=False)+';module.exports='+version+';')
            f.close()
    else:
        # write real JSON file
        print(f'{version} - writing JSON file')
        with open(exists_obj['filename'], 'w', encoding=encoding) as f:
            json.dump(bible, f, ensure_ascii=False)

    # pretty partial JSON file, only used for understanding JSON structure
    if partials:
        for book in bible['books']:
            is_genesis = book['name'].lower().startswith('ge') or book['name'].lower().startswith('gn')

            # to understand JSON structure, verses per chapter is generally too much info
            if is_genesis:
                book['verses_per_chapter'] = book['verses_per_chapter'][:3]
            else:
                book['verses_per_chapter'] = []

            # to understand JSON structure, we only want certain verses
            for chapter in book['chapters']:
                if is_genesis and chapter['number'] == 1:
                    chapter['verses'] = chapter['verses'][:3]
                elif is_genesis and chapter['number'] == 3:
                    chapter['verses'] = [chapter['verses'][19]]  # Gen 3:20 KJV is first \u2019 - And Adam ..
                elif is_genesis and chapter['number'] == 4:
                    chapter['verses'] = [chapter['verses'][21]]  # Gen 4:22 KJV is first \u2013 - And Zillah ..
                else:
                    chapter['verses'] = []

        # write partial JSON file
        partial_filename = re.sub('.json$', '-partial.json', exists_obj['filename'])
        with open(partial_filename, 'w', encoding=encoding) as f:
            f.write(json.dumps(bible, indent=2, ensure_ascii=False))
