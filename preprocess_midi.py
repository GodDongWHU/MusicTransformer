import argparse
import os
import pickle
import json
import random
from pathlib import Path

import third_party.midi_processor.processor as midi_processor

JSON_FILE = "maestro-v2.0.0.json"

# prep_midi
def prep_maestro_midi(maestro_root, output_dir):
    """
    ----------
    Author: Damon Gwinn
    ----------
    Pre-processes the maestro dataset, putting processed midi data (train, eval, test) into the
    given output folder
    ----------
    """

    train_dir = os.path.join(output_dir, "train")
    os.makedirs(train_dir, exist_ok=True)
    val_dir = os.path.join(output_dir, "val")
    os.makedirs(val_dir, exist_ok=True)
    test_dir = os.path.join(output_dir, "test")
    os.makedirs(test_dir, exist_ok=True)

    maestro_json_file = os.path.join(maestro_root, JSON_FILE)
    if(not os.path.isfile(maestro_json_file)):
        print("ERROR: Could not find file:", maestro_json_file)
        return False

    maestro_json = json.load(open(maestro_json_file, "r"))
    print("Found", len(maestro_json), "pieces")
    print("Preprocessing...")

    total_count = 0
    train_count = 0
    val_count   = 0
    test_count  = 0

    vocab_note_all = set()
    vocab_duration_all = set()
    vocab_chord_all = set()

    for piece in maestro_json:
        mid         = os.path.join(maestro_root, piece["midi_filename"])
        split_type  = piece["split"]
        f_name      = mid.split("/")[-1] + ".pickle"

        if(split_type == "train"):
            o_file = os.path.join(train_dir, f_name)
            train_count += 1
        elif(split_type == "validation"):
            o_file = os.path.join(val_dir, f_name)
            val_count += 1
        elif(split_type == "test"):
            o_file = os.path.join(test_dir, f_name)
            test_count += 1
        else:
            print("ERROR: Unrecognized split type:", split_type)
            return False

        # prepped = midi_processor.encode_midi(mid)
        prepped, vocab_note, vocab_duration, vocab_chord = midi_processor.encode_midi_music21(mid)
        
        vocab_note_all = vocab_note_all | vocab_note
        vocab_duration_all = vocab_duration_all | vocab_duration
        vocab_chord_all = vocab_chord_all | vocab_chord

        o_stream = open(o_file, "wb")
        pickle.dump(prepped, o_stream)
        o_stream.close()

        total_count += 1
        if(total_count % 50 == 0):
            print(total_count, "/", len(maestro_json))

    print("Num Train:", train_count)
    print("Num Val:", val_count)
    print("Num Test:", test_count)

    vocab_note_all = {key: index for index, key in enumerate(vocab_note_all)}
    vocab_duration_all = {key: index for index, key in enumerate(vocab_duration_all)}
    vocab_chord_all = {key: index for index, key in enumerate(vocab_chord_all)}
    print("vocab_note:", vocab_note_all)
    print("vocab_duration:", vocab_duration_all)
    print("vocab_chord:", vocab_chord_all)
    # o_stream = open(output_dir + "\\vocab.pickle", "wb")
    # pickle.dump(vocab_note, o_stream)
    # pickle.dump(vocab_duration, o_stream)
    # pickle.dump(vocab_chord, o_stream)
    # o_stream.close()

    # try:
    #     with open(output_dir + "\\vocab.pickle", 'rb') as f:
    #         vocab_note = pickle.load(f)
    #         vocab_note = {key: index for index, key in enumerate(vocab_note)}
    #         vocab_duration = pickle.load(f)
    #         vocab_duration = {key: index for index, key in enumerate(vocab_duration)}
    #         vocab_chord = pickle.load(f)
    #         vocab_chord = {key: index for index, key in enumerate(vocab_chord)}
    # except Exception as e:
    #     print(f"Failed to load pickle file: {e}")
    
    dataset_list = ["train", "test", "val"]
    for type in dataset_list:
        path_train = Path(os.path.join(output_dir, type))
        for file_path in path_train.rglob("*"):  # 匹配所有文件和子文件夹
            if file_path.is_file():
                with open(file_path, 'rb') as i_stream:
                    data = pickle.load(i_stream)
                    notes = data['notes']
                    durations = data['durations']
                    chords = data['chords']
                    replaced_notes = [vocab_note_all.get(note, note) for note in notes]
                    replaced_durations = [vocab_duration_all.get(duration, duration) for duration in durations]
                    replaced_chords = [vocab_chord_all.get(chord, chord) for chord in chords]
                replaced_data = {"notes": replaced_notes, "durations": replaced_durations, "chords": replaced_chords}
                print("Replacing: " + str(file_path))
                with open(file_path, 'wb') as o_stream:
                    pickle.dump(replaced_data, o_stream)

    print("Write vocab to dict...")
    with open(output_dir + "\\vocab.pickle", "wb") as o_stream:
        pickle.dump(vocab_note_all, o_stream)
        pickle.dump(vocab_duration_all, o_stream)
        pickle.dump(vocab_chord_all, o_stream)

    return True

def prep_custom_midi(custom_midi_root, output_dir, valid_p = 0.1, test_p = 0.2):
    """
    ----------
    Author: Corentin Nelias
    ----------
    Pre-processes custom midi files that are not part of the maestro dataset, putting processed midi data (train, eval, test) into the
    given output folder. 
    ----------
    """
    train_dir = os.path.join(output_dir, "train")
    os.makedirs(train_dir, exist_ok=True)
    val_dir = os.path.join(output_dir, "val")
    os.makedirs(val_dir, exist_ok=True)
    test_dir = os.path.join(output_dir, "test")
    os.makedirs(test_dir, exist_ok=True)
    
    print("Found", len(os.listdir(custom_midi_root)), "pieces")
    print("Preprocessing custom data...")
    total_count = 0
    train_count = 0
    val_count   = 0
    test_count  = 0
    
    for piece in os.listdir(custom_midi_root):
        #deciding whether the data should be part of train, valid or test dataset
        is_train = True if random.random() > valid_p else False
        if not is_train:
            is_valid = True if random.random() > test_p else False
        if is_train:
            split_type  = "train"
        elif is_valid:
            split_type = "validation"
        else:
            split_type = "test"
            
        mid         = os.path.join(custom_midi_root, piece)
        f_name      = piece.split(".")[0] + ".pickle"

        if(split_type == "train"):
            o_file = os.path.join(train_dir, f_name)
            train_count += 1
        elif(split_type == "validation"):
            o_file = os.path.join(val_dir, f_name)
            val_count += 1
        elif(split_type == "test"):
            o_file = os.path.join(test_dir, f_name)
            test_count += 1
        
        # prepped = midi_processor.encode_midi(mid)
        prepped = midi_processor.encode_midi_music21(mid)

        o_stream = open(o_file, "wb")
        pickle.dump(prepped, o_stream)
        o_stream.close()

        total_count += 1
        if(total_count % 50 == 0):
            print(total_count, "/", len(os.listdir(custom_midi_root)))

    print("Num Train:", train_count)
    print("Num Val:", val_count)
    print("Num Test:", test_count)
    return True


# parse_args
def parse_args():
    """
    ----------
    Author: Damon Gwinn
    ----------
    Parses arguments for preprocess_midi using argparse
    ----------
    """

    parser = argparse.ArgumentParser()

    parser.add_argument("root", type=str, help="Root folder for the Maestro dataset or for custom data.")
    parser.add_argument("-output_dir", type=str, default="./dataset/e_piano", help="Output folder to put the preprocessed midi into.")
    parser.add_argument("--custom_dataset", action="store_true", help="Whether or not the specified root folder contains custom data.")

    return parser.parse_args()

# main
def main():
    """
    ----------
    Author: Damon Gwinn
    ----------
    Entry point. Preprocesses maestro and saved midi to specified output folder.
    ----------
    """

    args            = parse_args()
    root    = args.root
    output_dir      = args.output_dir

    print("Preprocessing midi files and saving to", output_dir)
    if args.custom_dataset:
        prep_custom_midi(root, output_dir)
    else:
        prep_maestro_midi(root, output_dir)
    print("Done!")
    print("")

if __name__ == "__main__":
    main()
