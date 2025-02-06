import pretty_midi
import music21


RANGE_NOTE_ON = 128
RANGE_NOTE_OFF = 128
RANGE_VEL = 32
RANGE_TIME_SHIFT = 100

START_IDX = {
    'note_on': 0,
    'note_off': RANGE_NOTE_ON,
    'time_shift': RANGE_NOTE_ON + RANGE_NOTE_OFF,
    'velocity': RANGE_NOTE_ON + RANGE_NOTE_OFF + RANGE_TIME_SHIFT
}

parser = music21.converter

class SustainAdapter:
    def __init__(self, time, type):
        self.start =  time
        self.type = type


class SustainDownManager:
    def __init__(self, start, end):
        self.start = start
        self.end = end
        self.managed_notes = []
        self._note_dict = {} # key: pitch, value: note.start

    def add_managed_note(self, note: pretty_midi.Note):
        self.managed_notes.append(note)

    def transposition_notes(self):
        for note in reversed(self.managed_notes):
            try:
                note.end = self._note_dict[note.pitch]
            except KeyError:
                note.end = max(self.end, note.end)
            self._note_dict[note.pitch] = note.start


# Divided note by note_on, note_off
class SplitNote:
    def __init__(self, type, time, value, velocity):
        ## type: note_on, note_off
        self.type = type
        self.time = time
        self.velocity = velocity
        self.value = value

    def __repr__(self):
        return '<[SNote] time: {} type: {}, value: {}, velocity: {}>'\
            .format(self.time, self.type, self.value, self.velocity)


class Event:
    def __init__(self, event_type, value):
        self.type = event_type
        self.value = value

    def __repr__(self):
        return '<Event type: {}, value: {}>'.format(self.type, self.value)

    def to_int(self):
        return START_IDX[self.type] + self.value

    @staticmethod
    def from_int(int_value):
        info = Event._type_check(int_value)
        return Event(info['type'], info['value'])

    @staticmethod
    def _type_check(int_value):
        range_note_on = range(0, RANGE_NOTE_ON)
        range_note_off = range(RANGE_NOTE_ON, RANGE_NOTE_ON+RANGE_NOTE_OFF)
        range_time_shift = range(RANGE_NOTE_ON+RANGE_NOTE_OFF,RANGE_NOTE_ON+RANGE_NOTE_OFF+RANGE_TIME_SHIFT)

        valid_value = int_value

        if int_value in range_note_on:
            return {'type': 'note_on', 'value': valid_value}
        elif int_value in range_note_off:
            valid_value -= RANGE_NOTE_ON
            return {'type': 'note_off', 'value': valid_value}
        elif int_value in range_time_shift:
            valid_value -= (RANGE_NOTE_ON + RANGE_NOTE_OFF)
            return {'type': 'time_shift', 'value': valid_value}
        else:
            valid_value -= (RANGE_NOTE_ON + RANGE_NOTE_OFF + RANGE_TIME_SHIFT)
            return {'type': 'velocity', 'value': valid_value}


def _divide_note(notes):
    result_array = []
    notes.sort(key=lambda x: x.start)

    for note in notes:
        on = SplitNote('note_on', note.start, note.pitch, note.velocity)
        off = SplitNote('note_off', note.end, note.pitch, None)
        result_array += [on, off]
    return result_array


def _merge_note(snote_sequence):
    note_on_dict = {}
    result_array = []

    for snote in snote_sequence:
        # print(note_on_dict)
        if snote.type == 'note_on':
            note_on_dict[snote.value] = snote
        elif snote.type == 'note_off':
            try:
                on = note_on_dict[snote.value]
                off = snote
                if off.time - on.time == 0:
                    continue
                result = pretty_midi.Note(on.velocity, snote.value, on.time, off.time)
                result_array.append(result)
            except:
                print('info removed pitch: {}'.format(snote.value))
    return result_array


def _snote2events(snote: SplitNote, prev_vel: int):
    result = []
    if snote.velocity is not None:
        modified_velocity = snote.velocity // 4
        if prev_vel != modified_velocity:
            result.append(Event(event_type='velocity', value=modified_velocity))
    result.append(Event(event_type=snote.type, value=snote.value))
    return result


def _event_seq2snote_seq(event_sequence):
    timeline = 0
    velocity = 0
    snote_seq = []

    for event in event_sequence:
        if event.type == 'time_shift':
            timeline += ((event.value+1) / 100)
        if event.type == 'velocity':
            velocity = event.value * 4
        else:
            snote = SplitNote(event.type, timeline, event.value, velocity)
            snote_seq.append(snote)
    return snote_seq


def _make_time_sift_events(prev_time, post_time):
    time_interval = int(round((post_time - prev_time) * 100))
    results = []
    while time_interval >= RANGE_TIME_SHIFT:
        results.append(Event(event_type='time_shift', value=RANGE_TIME_SHIFT-1))
        time_interval -= RANGE_TIME_SHIFT
    if time_interval == 0:
        return results
    else:
        return results + [Event(event_type='time_shift', value=time_interval-1)]


def _control_preprocess(ctrl_changes):
    sustains = []

    manager = None
    for ctrl in ctrl_changes:
        if ctrl.value >= 64 and manager is None:
            # sustain down
            manager = SustainDownManager(start=ctrl.time, end=None)
        elif ctrl.value < 64 and manager is not None:
            # sustain up
            manager.end = ctrl.time
            sustains.append(manager)
            manager = None
        elif ctrl.value < 64 and len(sustains) > 0:
            sustains[-1].end = ctrl.time
    return sustains


def _note_preprocess(susteins, notes):
    note_stream = []

    if susteins:    # if the midi file has sustain controls
        for sustain in susteins:
            for note_idx, note in enumerate(notes):
                if note.start < sustain.start:
                    note_stream.append(note)
                elif note.start > sustain.end:
                    notes = notes[note_idx:]
                    sustain.transposition_notes()
                    break
                else:
                    sustain.add_managed_note(note)

        for sustain in susteins:
            note_stream += sustain.managed_notes
    
    else:       # else, just push everything into note stream
        for note_idx, note in enumerate(notes):
            note_stream.append(note)

    note_stream.sort(key= lambda x: x.start)
    return note_stream


def encode_midi(file_path):
    events = []
    notes = []
    mid = pretty_midi.PrettyMIDI(midi_file=file_path)

    for inst in mid.instruments:
        inst_notes = inst.notes
        # ctrl.number is the number of sustain control. If you want to know abour the number type of control,
        # see https://www.midi.org/specifications-old/item/table-3-control-change-messages-data-bytes-2
        ctrls = _control_preprocess([ctrl for ctrl in inst.control_changes if ctrl.number == 64])
        notes += _note_preprocess(ctrls, inst_notes)

    dnotes = _divide_note(notes)

    # print(dnotes)
    dnotes.sort(key=lambda x: x.time)
    # print('sorted:')
    # print(dnotes)
    cur_time = 0
    cur_vel = 0
    for snote in dnotes:
        events += _make_time_sift_events(prev_time=cur_time, post_time=snote.time)
        events += _snote2events(snote=snote, prev_vel=cur_vel)
        # events += _make_time_sift_events(prev_time=cur_time, post_time=snote.time)

        cur_time = snote.time
        cur_vel = snote.velocity

    return [e.to_int() for e in events]

def encode_midi_music21(file_path):
    # file_path = "C:\\Users\\76462\\Downloads\\bach-air-mids\\bach-air-violin1.mid"
    notes = []
    durations = []
    chords = []

    score = parser.parse(file_path).chordify()   # 解析每个文件并将其转化为和弦形式（方便处理复杂的多音轨音乐）

    notes.append("START")       # 初始化 notes 和 durations
    durations.append("0.0")
    chords.append("0")

    # flat 是 music21 的一个方法，用于将嵌套的音乐对象展开成一个平坦的序列。这样，乐谱中的每个元素（音符、和弦、休止符等）可以逐个处理。
    for element in score.flat:
        note_name = None
        duration_name = None
        chord_name = None

        # 主音（tonic）和模式（mode，如大调或小调）
        if isinstance(element, music21.key.Key):
            # 如果调性是 C 大调，note_name = "C:maj"，时值为 "0.0"（因为调性信息本身没有时值）。
            note_name = str(element.tonic.name) + ":" + str(element.mode)
            duration_name = "0.0"
            chord_name = "0"

        elif isinstance(element, music21.meter.TimeSignature):
            # 提取拍号的比例字符串（如 "4/4"）并附加 "TS" 标记。如果拍号是 4/4，note_name = "4/4TS"，时值为 "0.0"。
            note_name = str(element.ratioString) + "TS"
            duration_name = "0.0"
            chord_name = "0"

        elif isinstance(element, music21.chord.Chord):
            # 选取和弦中最低音(一般是根音)，提取它的音高和八度信息（如C4）。
            # 示例：C和弦（C4-E4-G4）持续两拍，note_name = "C4"，duration_name = "2.0"
            note_name = element.pitches[0].nameWithOctave
            if len(element.pitches) > 1:
                # 处理和弦
                chord_name = element.commonName
            else:
                # 处理单音符
                chord_name = "0"
            duration_name = str(element.duration.quarterLength)

        elif isinstance(element, music21.note.Rest):
            # 提取休止符的名称（通常是 "rest"）和时值。如四分休止符，note_name = "rest"，duration_name = "1.0"。
            note_name = str(element.name)
            duration_name = str(element.duration.quarterLength)
            chord_name = "0"

        elif isinstance(element, music21.note.Note):
            # music21.note.Note 表示单个音符
            # 示例：C4 持续一拍，note_name = "C4"，duration_name = "1.0"
            note_name = str(element.nameWithOctave)
            duration_name = str(element.duration.quarterLength)
            chord_name = "0"

        if note_name and duration_name and chord_name:
            notes.append(note_name)
            durations.append(duration_name)
            chords.append(chord_name)
    print(f"{len(notes)} notes parsed")

    note_pairs = {"notes": notes, "durations": durations, "chords": chords}
    vocab_note = set(notes)
    vocab_duration = set(durations)
    vocab_chord = set(chords)

    return note_pairs, vocab_note, vocab_duration, vocab_chord


def decode_midi(idx_array, file_path=None):
    event_sequence = [Event.from_int(idx) for idx in idx_array]
    # print(event_sequence)
    snote_seq = _event_seq2snote_seq(event_sequence)
    note_seq = _merge_note(snote_seq)
    note_seq.sort(key=lambda x:x.start)

    mid = pretty_midi.PrettyMIDI()
    # if want to change instument, see https://www.midi.org/specifications/item/gm-level-1-sound-set
    instument = pretty_midi.Instrument(1, False, "Developed By Yang-Kichang")
    instument.notes = note_seq

    mid.instruments.append(instument)
    if file_path is not None:
        mid.write(file_path)
    return mid


if __name__ == '__main__':
    encoded = encode_midi('bin/ADIG04.mid')
    print(encoded)
    decided = decode_midi(encoded,file_path='bin/test.mid')

    ins = pretty_midi.PrettyMIDI('bin/ADIG04.mid')
    print(ins)
    print(ins.instruments[0])
    for i in ins.instruments:
        print(i.control_changes)
        print(i.notes)