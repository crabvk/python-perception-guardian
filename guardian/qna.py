import random


class Query:
    def __init__(self, emoji: str, phrase: str | list):
        self.emoji = emoji
        self.phrase = phrase

    def pick_emoji(self):
        if len(self.emoji) == 1:
            return self.emoji
        else:
            return random.choice(self.emoji)

    def pick_phrase(self):
        if isinstance(self.phrase, str):
            return self.phrase
        else:
            return random.choice(self.phrase)

    def __repr__(self):
        return f'{self.__class__.__name__}(emoji={self.emoji!r} phrase={self.phrase!r})'


class Combination:
    def __init__(self, emoji: list, answer_index: int, query_phrase: str):
        self.emoji = emoji
        self.answer_index = answer_index
        self.query_phrase = query_phrase

    def answer(self):
        return self.emoji[self.answer_index]

    def __repr__(self):
        return f'{self.__class__.__name__}(emoji={self.emoji!r} answer_index={self.answer_index!r} query_phrase={self.query_phrase!r})'


# autopep8: off
QNA = [
    Query('😎🕶', 'people in sunglasses'),
    Query('🥳🎉🎊', ('birthday party children', 'people on a party')),
    Query('😤😠😡', 'angry man'),
    Query('🤗', ('hug', 'hugging')),
    Query('🤔', 'thinking man'),
    Query('🥴🍺🍻🥂🥃', ('drunk man', 'drinking alcohol')),
    Query('🤢🤮', 'vomit in cartoon'),
    Query('🤧😷🤒🤕', 'sick man'),
    Query('🤑💰💸💵', ('money economics', 'dollars')),
    [
        Query('🤠', 'cowboy'),
        Query('🐴🐎', 'horse'),
    ],
    Query('😈👹', 'devil'),
    Query('🤡', 'clown'),
    Query('💩', 'poop in cartoon'),
    Query('👻', 'ghost'),
    Query(('💀','☠️'), 'skull'),
    Query('👽', ('alien', 'ufo')),
    Query('🤖', 'robot'),
    Query('🎃', ('halloween', 'pumpkin')),
    Query('😺🐈', ('cat', 'kitty')),
    Query('🤝', 'handshake'),
    Query(('👍', '👍🏻', '👍🏼'), 'people thumbs up'),
    Query(('👎', '👎🏻', '👎🏼'), 'people thumbs down sad'),
    Query(('💪', '💪🏻', '💪🏼'), 'strong man in gym'),
    Query(('🖕', '🖕🏻', '🖕🏼'), 'middle finger'),
    Query(('✍️', '✍🏻', '✍🏼'), 'writing'),
    Query(('🦶', '🦶🏻', '🦶🏼'), 'foot'),
    Query(('👂', '👂🏻', '👂🏼'), 'ear'),
    Query(('👃', '👃🏻', '👃🏼'), 'pictures of nose'),
    Query(('👶', '👶🏻', '👶🏼'), 'child'),
    [
        Query(('🧔🏻‍♀️', '🧔', '🧔🏻', '🧔‍♂️', '🧔🏻‍♂️'), 'beard'),
        Query(('👴', '👴🏻', '👴🏼'), 'old man'),
        Query(('👵', '👵🏻', '👵🏼', '🧓', '🧓🏻', '🧓🏼'), 'old lady'),
    ],
    Query(('👮‍♀️', '👮🏻‍♀️', '👮🏼‍♀️', '👮', '👮🏻', '👮🏼', '👮‍♂️', '👮🏻‍♂️', '👮🏼‍♂️'), 'police uniform'),
    Query(('👩‍💻', '👩🏻‍💻', '👩🏼‍💻', '🧑‍💻', '🧑🏻‍💻', '🧑🏼‍💻', '👨‍💻', '👨🏻‍💻', '👨🏼‍💻'), 'programmer with computer'),
    Query(('👩‍🚒', '👩🏻‍🚒', '👩🏼‍🚒', '🧑‍🚒', '🧑🏻‍🚒', '🧑🏼‍🚒', '👨‍🚒', '👨🏻‍🚒', '👨🏼‍🚒'), 'fireman at work'),
    Query(('👩‍🚀', '👩🏻‍🚀', '👩🏼‍🚀', '🧑‍🚀', '🧑🏻‍🚀', '🧑🏼‍🚀', '👨‍🚀', '👨🏻‍🚀', '👨🏼‍🚀'), 'spaceman'),
    Query(('👰‍♀️', '👰🏻‍♀️', '👰🏼‍♀️', '👰', '👰🏻', '👰🏼', '👰‍♂️', '👰🏻‍♂️', '👰🏼‍♂️'), 'wife in wedding dress'),
    Query(('🤴', '🤴🏻', '🤴🏼', '👑'), ('king with a crown', 'crown')),
    Query(('🎅', '🎅🏻', '🎅🏼'), 'santa clause'),
    Query(('🤦‍♂️', '🤦🏻‍♂️', '🤦🏼‍♂️'), 'facepalm'),
    Query(('🤷‍♀️', '🤷🏻‍♀️', '🤷🏼‍♀️', '🤷‍♂️', '🤷🏻‍♂️', '🤷🏼‍♂️'), 'shrugging hands'),
]
# autopep8: on


def _pick_query(q: Query | list) -> Query:
    if isinstance(q, list):
        return random.choice(q)
    else:
        return q


def pick(count: int):
    sample = random.sample(QNA, count)
    queries = tuple(map(_pick_query, sample))
    emoji = tuple(map(lambda q: q.pick_emoji(), queries))
    answer_idx = random.randrange(0, count)
    query_phrase = queries[answer_idx].pick_phrase()
    return Combination(emoji, answer_idx, query_phrase)
