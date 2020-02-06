import argparse
import time
from pathlib import Path
from pysword.modules import SwordModules
from py.helpers import does_bible_json_exist
from py.helpers import write_bible_json
from py.Report import Report
from py.versions import lookup_version_abbr, lookup_version_name
from xml.dom import minidom

# from pprint import pprint  # pprint(vars(book))
default_encoding = 'utf-8'

def getStrongsFromNode(node):
    try:
        lemmaString = node.attributes['lemma']
        lemmaArray=[]
        for lemma in lemmaString.value.split(' '):
            try:
                lemma.index('lemma')
            except:
                lemmaArray.append(lemma.replace('strong:H0', 'H').replace('strong:G','G'))

        return ' '.join(lemmaArray)
    except:
        return ''

def getMorphFromNode(node):
    try:
        return node.attributes['morph'].value.replace('strongMorph:TH', 'TH').replace('robinson:', '')
    except:
        return ''

def getTextArrayFromNode(node, verseArray):
    word = '';
    strongs = '';
    morph = '';
    if node.nodeName == 'w':
        strongs = getStrongsFromNode(node)
        morph = getMorphFromNode(node)
        for w in node.childNodes:
            word = w.nodeValue
            if strongs == 'H3068' or strongs == 'H3069' or strongs == 'H3050': # an exception for divinename in the kjv
                if w.nodeName == '#text':
                    word = w.nodeValue.strip()
                    verseArray.append( [ word ] )
                if w.nodeName == 'divineName':
                    verseArray = getTextArrayFromNode(w, verseArray)
                    for u in w.childNodes:
                        if u.nodeName == '#text':
                            word = u.nodeValue.strip()

    if node.nodeName == '#text':
        word = node.nodeValue
    if node.nodeName == 'transChange':
        word = node.childNodes[0].nodeValue
        strongs = node.attributes['type'].value
    if node.nodeName == 'divineName':
        for u in node.childNodes:
            if u.nodeName == 'w':
                strongs = getStrongsFromNode(u)
                morph = getMorphFromNode(node)
                for x in u.childNodes:
                    word = x.nodeValue
            elif u.nodeName == '#text':
                word = u.nodeValue
                strongs = 'added divineName'

    if word is None:
        word=''
    else:
        word=word.strip()

    textArray = None
    if word != '' and word != ' ':
        textArray = [ word ]
        if strongs != '':
            textArray = [ word, strongs ]
        if morph != '':
            textArray = [ word, strongs, morph ]

    if textArray is not None:
        verseArray.append( textArray )
    return verseArray

def getWordArrayFromNodes( bookName, nodes, verseArray ):
    for node in nodes:
        if bookName == 'Psalms' and node.nodeName == 'title':
            for childNode in node.childNodes:
                verseArray = getTextArrayFromNode(childNode, verseArray)
        elif node.nodeName == 'q':
            for childNode in node.childNodes:
                verseArray = getTextArrayFromNode(childNode, verseArray)
        else:
            verseArray = getTextArrayFromNode(node, verseArray)
    return verseArray


def getTextAsXML( text ):
    xmldoc = minidom.parseString('<v>'+text+'</v>')
    textAsXML = xmldoc.getElementsByTagName('v')
    return textAsXML[0].childNodes

# noinspection PyProtectedMember
def get_bible_json(path, overwrite, npm):
    # load sword module
    modules = SwordModules(path)
    found_modules = modules.parse_modules()
    keys = found_modules.keys()
    assert len(keys) == 1
    sword_version = list(keys)[0]
    version = lookup_version_abbr(sword_version)
    module = found_modules[sword_version]
    report = Report(version)

    print('==================================================')
    print(f'{version} - processing in progress, please wait')
    # pprint(module)

    # get metadata
    language = module['lang']
    meta = {
        'description': module['description'] if module.get('description') and 'Strong' not in module['description'] else None,
        'source': 'sword',
        'swordVersion': module.get('version'),
        'swordVersionDate': module.get('swordversiondate'),
        'encoding': module['encoding'].lower() if module.get('encoding') else None,
        'language': language,
        'license': module['distributionlicense'] if module.get('distributionlicense') and 'Strong' not in module['distributionlicense'] else None,
        'copyright': module.get('copyright') or module.get('shortcopyright')
    }

    actual_encoding = meta['encoding']
    assert actual_encoding == default_encoding or actual_encoding is None, f'{version} - expected module encoding {default_encoding} but got {actual_encoding}'

    # skip if JSON exists
    exists_obj = does_bible_json_exist(version, language)
    if exists_obj['exists'] and not overwrite:
        print(f'{version} - skipping, already exists')
        return None

    # get raw bible books
    # noinspection PyBroadException
    try:
        bible = modules.get_bible_from_module(sword_version)
    except Exception as e:
        print(f'{version} - aborting, pysword failure .. {e}')
        return None

    assert bible._encoding == default_encoding or bible._encoding is None, f'{version} - expected bible encoding {default_encoding} but got {bible._encoding}'
    bible_structure = bible.get_structure()
    assert bible_structure._book_offsets is None

    if bible_structure._books.get('ot') is None:
        print(f'{version} - aborting, old testament missing')
        return None

    if bible_structure._books.get('nt') is None:
        print(f'{version} - aborting, new testament missing')
        return None

    raw_books = bible_structure._books['ot'] + bible_structure._books['nt']
    assert len(raw_books) == 66

    # init processing
    start = time.time()
    chapter_count = 0
    verse_count = 0

    # main processing
    books = []
    booksObj={}
    for book_idx, book in enumerate(raw_books):

        report.processed(book_idx + 1, book.osis_name, start)
        range_chapters = range(0, book.num_chapters)

        chapters = []
        chaptersObj=[]
        for chapter_idx in range_chapters:

            chapter_num = chapter_idx + 1
            raw_verses = book.get_indicies(chapter_num)

            verses = []
            versesObj = []
            for verse_idx, xxxxx in enumerate(raw_verses):

                verse_num = verse_idx + 1

                try:
                    text = bible.get(books=[book.name], chapters=[chapter_num], verses=[verse_num], clean=True)
                    textAsXML = getTextAsXML( bible.get(books=[book.name], chapters=[chapter_num], verses=[verse_num], clean=False) )
                    verseArray = getWordArrayFromNodes( book.name, textAsXML, [] );

                except Exception as e:
                    if 'incorrect header' in str(e):
                        text = None
                    else:
                        raise e

                # if text is not None and version == 'ASV':
                #     text = text.encode('latin-1').decode('cp1252')

                if text is not None:
                    # TIDYUP - trim
                    text = text.strip()

                if text == '':
                    text = None

                if text is not None:

                    # TIDYUP - remove double spaces
                    while '  ' in text:
                        text = text.replace('  ', ' ')

                    # TIDYUP - replace horrible chars
                    text = text.replace('\u2013', '-')
                    text = text.replace('\u2019', '\'')

                verses.append({
                    'number': verse_num,
                    'text': text
                })
                verse_count += 1
                versesObj.append(verseArray)

            chapters.append({
                'number': chapter_num,
                'verses': verses
            })
            chapter_count += 1
            chaptersObj.append(versesObj)

        books.append({
            'name': book.osis_name,
            'verses_per_chapter': book.chapter_lengths,
            'chapters': chapters,
        })
        booksObj[book.name] = chaptersObj

    print()
    report.summary(len(books), chapter_count, verse_count)
    assert chapter_count == 1189
    if npm:
        books = booksObj
 
    return {
        'version': version,
        'versionName': lookup_version_name(sword_version),
        'meta': meta,
        'books': books
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--overwrite', action='store_true')
    parser.add_argument('--partials', action='store_true')
    parser.add_argument('--npm', action='store_true')
    args = parser.parse_args()
    overwrite = args.overwrite
    partials = args.partials
    npm = args.npm

    paths = Path('sword-modules').glob('**/*.zip')
    for path in paths:
        bible = get_bible_json(str(path), overwrite, npm)
        if bible is not None:
            write_bible_json(bible, partials, npm)


if __name__ == '__main__':
    main()
