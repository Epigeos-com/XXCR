from cricodecs import hca, adx, usm
import sys
import os
import shutil
from ffmpeg import FFmpeg
import zipfile
import io
import subprocess
import platform
from glob import glob

# TODO: Separate enabling/disabling mods from applying/reverting
# TODO: Optimise space usage for mods
# TODO: Fix trailing slash breaking things in <mod_name> inputs

def print_help():
    print("\nUsage:")
    print("\n   XXCR.py config")
    print("\n   XXCR.py apply <mod_dir_or_file>")
    print("\n   XXCR.py revert (GI|ZZ|SR)")
    print("\n   XXCR.py create <mod_name> (GI|ZZ|SR)")
    print("\n   XXCR.py file <mod_name> <cutscene_name> (-v <video_file>) (-cn <audio_file>) (-en <audio_file>) (-jp <audio_file>) (-kr <audio_file>) (-a <audio_file>)")
    print("      NOTE: Pass 'r' instead of a file path to remove the file.")
    print("      NOTE: Any file format that can be converted by ffmpeg into ivf for video or wav for audio is supported.")
    print("      NOTE: Files that have a very different resolution than the original may break.")
    print("      NOTE: Files passed with -a are treated as a kind of default, the language-specific choices override them.")
    print("      NOTE: You can provide multiple comma-separated cutscene names to apply the same changes to all of them.")
    print("\n   XXCR.py export <mod_name>")
    print("\n   XXCR.py extract (GI|ZZ|SR) <comma_separated_cutscene_names> (-cv <target_video_format>) (-ca <target_audio_format>)")
    print("\n   XXCR.py cutscenes (GI|ZZ|SR) (<separator>)")
    print("      NOTE: Displays all available cutscenes.")

game_id_from_name = {"gi": 0, "zz": 1, "sr": 2}
def get_config():
    try:
        with open("config.txt", "r") as file:
            return file.readlines()
    except:
        raise Exception('Please run `XXCR.py config` first.')
def get_mod_game(mod_name):
    try:
        with open(mod_name + "/.game", "r") as file:
            return file.read()
    except:
        raise Exception('Mod ' + mod_name + ' doesn\'t exist or doesn\'t contain .game')
def get_mod_game_video_assets_location(mod):
    return get_config()[game_id_from_name[get_mod_game(mod)]][:-1]

def cp(src, dst):
    if (platform.system() == "Linux"):
        subprocess.run(['cp', src, dst])
    else:
        shutil.copy(src, dst)

def main():
    if (len(sys.argv) == 1):
        print_help()
    else:
        if (sys.argv[1] == "config"):
            for game, location in [["GI", ".../GenshinImpact_Data/StreamingAssets/VideoAssets/StandaloneWindows64/"], ["ZZ", ".../ZenlessZoneZero_Data/StreamingAssets/Video/HD/"], ["SR", ".../StarRail_Data/StreamingAssets/Video/Windows/"]]:
                while True:
                    print("\n   NOTE: Should be at `" + location + "`")
                    print("   NOTE: Leave empty if you're not gonna be modifying " + game)
                    directory = input(game + ' video assets directory: ')
                    if (directory != ""):
                        has_usm_file = False
                        for file_name in os.listdir(directory):
                            if file_name.endswith('.usm'):
                                has_usm_file = True
                                break
                        if (not has_usm_file):
                            print("\n\nNo .usm file found in `" + directory + "`.\n")
                            continue
                    with open("config.txt", "a") as file:
                        file.write(directory + "\n")
                    break
        elif (sys.argv[1] == "create"):
            if (len(sys.argv) <= 3 or not sys.argv[3].lower() in ['gi', 'zz', 'sr']):
                print("Not enough arguments or invalid game!")
                print_help()
                return

            os.mkdir(sys.argv[2])
            with open(sys.argv[2] + "/.game", "w") as game_file:
                game_file.write(sys.argv[3].lower())

            print("Created mod " + sys.argv[2] + " for game " + sys.argv[3].upper() + ".")
        elif (sys.argv[1] == "file"):
            if (len(sys.argv) <= 5):
                print("Not enough arguments!")
                print_help()
                return

            for cutscene_name in sys.argv[3].split(','):
                if (not os.path.isdir(sys.argv[2])):
                    raise Exception('Mod directory `' + sys.argv[2] + '` does not exist. Use XXCR.py create first.' )
                os.makedirs(sys.argv[2] + "/" + cutscene_name, exist_ok=True)

                game = get_mod_game(sys.argv[2])
                path_to_video_assets_dir = get_mod_game_video_assets_location(sys.argv[2])
                if (not os.path.isfile(path_to_video_assets_dir + "/" + cutscene_name + ".usm")):
                    raise Exception("Cutscene " + path_to_video_assets_dir + "/" + cutscene_name + ".usm not found.")

                try:
                    shutil.rmtree(sys.argv[2] + "/.temp")
                except:
                    pass
                os.mkdir(sys.argv[2] + "/.temp")

                for i in range(round(len(sys.argv[4:]) / 2)):
                    try:
                        with open(".local-" + sys.argv[2], "r") as local_file:
                            local_file_read = local_file.readlines()
                    except:
                        local_file_read = ""

                    arg = sys.argv[4:][i*2]
                    file = sys.argv[4:][i*2+1]
                    if (game == "gi"):
                        match arg:
                            case "-v":
                                target_file_name = os.path.basename(cutscene_name) + ".ivf"
                            case "-cn":
                                target_file_name = os.path.basename(cutscene_name) + "-CN.hca"
                            case "-en":
                                target_file_name = os.path.basename(cutscene_name) + "-EN.hca"
                            case "-jp":
                                target_file_name = os.path.basename(cutscene_name) + "-JP.hca"
                            case "-kr":
                                target_file_name = os.path.basename(cutscene_name) + "-KR.hca"
                            case "-a":
                                target_file_name = os.path.basename(cutscene_name) + ".hca"
                            case _:
                                raise Exception('Invalid argument: ' + arg)
                    elif (game == "zz"):
                        if (arg == "-v"):
                            target_file_name = os.path.basename(cutscene_name) + ".ivf"
                        else:
                            raise Exception('Invalid argument: ' + arg + '. For ZZZ only -v is available as audio is stored separately - use XXAR for audio instead.')
                    elif (game == "sr"):
                        match arg:
                            case "-v":
                                target_file_name = os.path.basename(cutscene_name) + ".ivf"
                            case "-cn":
                                target_file_name = os.path.basename(cutscene_name) + "-CN.adx"
                            case "-en":
                                target_file_name = os.path.basename(cutscene_name) + "-EN.adx"
                            case "-jp":
                                target_file_name = os.path.basename(cutscene_name) + "-JP.adx"
                            case "-kr":
                                target_file_name = os.path.basename(cutscene_name) + "-KR.adx"
                            case "-a":
                                target_file_name = os.path.basename(cutscene_name) + ".adx"
                            case _:
                                raise Exception('Invalid argument: ' + arg)
                    split_original = os.path.splitext(file)
                    split_target = os.path.splitext(target_file_name)
                    
                    path_to_final_target_file = sys.argv[2] + "/" + cutscene_name + "/" + target_file_name
                    if (file == "r" or os.path.isfile(path_to_final_target_file)):
                        with open(".local-" + sys.argv[2], "w") as local_file_write: # Remove from local file
                            for i in range(round(len(local_file_read)/2)):
                                if (local_file_read[2*i + 1] != path_to_final_target_file + "\n"):
                                    local_file_write.write(local_file_read[2*i] + local_file_read[2*i + 1])
                    
                    if (file == "r"):
                        os.remove(path_to_final_target_file)
                        try:
                            os.rmdir(sys.argv[2] + "/" + cutscene_name)
                        except:
                            pass
                        continue

                    local_file_line_index = -1
                    for i in range(round(len(local_file_read)/2)):
                        if (local_file_read[i*2] == file + "\n" and local_file_read[i*2 + 1].endswith(split_target[1] + "\n")):
                            local_file_line_index = i*2
                            break

                    if (local_file_line_index != -1):
                        path = local_file_read[local_file_line_index + 1][:-1]
                        print(file + " was already used for " + path + ". Copying.")
                        cp(path, path_to_final_target_file)
                    else:
                        if (split_target[1] == split_original[1]):
                            cp(file, sys.argv[2] + "/.temp/" + target_file_name)
                        else:
                            if (arg == "-v"):
                                print("Converting " + file + " with ffmpeg.")
                                ffmpeg = (
                                    FFmpeg()
                                    .option("y")
                                    .input(file)
                                    .output(
                                        sys.argv[2] + "/.temp/" + target_file_name,
                                        {"codec:v": "libvpx-vp9", "pix_fmt": "yuv420p"}
                                    )
                                )
                                ffmpeg.execute()
                            else:
                                wav_path = sys.argv[2] + "/.temp/" + split_target[0] + ".wav"
                                if (split_original[1] == ".wav"):
                                    cp(file, wav_path)
                                else:
                                    print("Converting " + file + " with ffmpeg.")
                                    ffmpeg = (
                                        FFmpeg()
                                        .option("y")
                                        .input(file)
                                        .output(wav_path)
                                    )
                                    ffmpeg.execute()
                                
                                if (game == "SR"):
                                    adx_config = adx.AdxEncodeConfig()
                                    adx_config.sample_rate = 48_000
                                    adx_config.channel_count = 2
                                    adx_config.encoding_mode = 3
                                    adx_config.block_size = 18
                                    adx_config.bit_depth = 4
                                    adx_config.highpass_freq = 500
                                    adx_config.version = 4
                                    with open(wav_path, "rb") as wav_file_rb:
                                        adx_bytes = hca.encode(wav_file_rb.read(), adx_config)
                                    with open(sys.argv[2] + "/.temp/" + target_file_name, "wb") as target_file_wb:
                                        target_file_wb.write(adx_bytes)
                                else:
                                    hca_config = hca.HcaEncodeConfig()
                                    hca_config.sample_rate = 48_000
                                    hca_config.channel_count = 2
                                    hca_config.quality = hca.HcaQuality.HIGH
                                    with open(wav_path, "rb") as wav_file_rb:
                                        hca_bytes = hca.encode(wav_file_rb.read(), hca_config)
                                    with open(sys.argv[2] + "/.temp/" + target_file_name, "wb") as target_file_wb:
                                        target_file_wb.write(hca_bytes)

                                os.remove(wav_path)

                        src_path = sys.argv[2] + "/.temp/" + target_file_name
                        dst_path = sys.argv[2] + "/" + cutscene_name + "/" + target_file_name
                        cp(src_path, dst_path)
                        os.remove(src_path)

                        with open(".local-" + sys.argv[2], "a") as local_file_append:
                            local_file_append.write(file + "\n" + path_to_final_target_file + "\n")
                    

                shutil.rmtree(sys.argv[2] + "/.temp")
        elif (sys.argv[1] == "extract"):
            if (len(sys.argv) <= 3 or not sys.argv[2].lower() in ['gi', 'zz', 'sr']):
                print("Not enough arguments or invalid game!")
                print_help()
                return

            convert_to_video_index = sys.argv.index("-cv") if "-cv" in sys.argv else None
            convert_to_audio_index = sys.argv.index("-ca") if "-ca" in sys.argv else None

            extracted_dir = sys.argv[2].upper() + "_extracted/"
            sound_file_extension = ".hca" if (sys.argv[2].lower() == "gi") else "adx"
            os.makedirs(extracted_dir, exist_ok=True)

            path_to_video_assets_dir = get_config()[game_id_from_name[sys.argv[2].lower()]][:-1]
            for cutscene_name in sys.argv[3].split(","):
                base_cutscene_name = os.path.basename(cutscene_name)
                usm_path = path_to_video_assets_dir + cutscene_name + ".usm"
                if (os.path.isfile(usm_path)):
                    print("Extracting " + cutscene_name)
                    cutscene_dir = extracted_dir + cutscene_name
                    os.makedirs(cutscene_dir)
                    sound_index = 0
                    languages = ["CN", "EN", "JP", "KR"]
                    usm_key = usm.recover_key(usm_path).candidates[0].key
                    demux = usm.demux(usm_path, key=usm_key)
                    for stream_name in demux.keys():
                        if (stream_name.endswith(sound_file_extension)):
                            sound_file_name = base_cutscene_name + "-" + languages[sound_index] + sound_file_extension
                            sound_file_path = cutscene_dir + "/" + sound_file_name
                            with open(sound_file_path, "wb") as file:
                                file.write(demux[stream_name])
                                sound_index += 1
                            if (convert_to_audio_index != None):
                                wav_file_path = sound_file_path[:-4] + ".wav"
                                sound_file_class = hca if (sound_file_extension == ".hca") else adx
                                with open(wav_file_path, "wb") as file:
                                    file.write(sound_file_class.decode(sound_file_path))
                                
                                os.makedirs(cutscene_dir + "/unconverted", exist_ok=True)
                                os.rename(sound_file_path, cutscene_dir + "/unconverted/" + sound_file_name)

                                format_to_convert_to = sys.argv[convert_to_audio_index + 1]
                                if (format_to_convert_to != "wav"):
                                    ffmpeg = (
                                        FFmpeg()
                                        .option("y")
                                        .input(wav_file_path)
                                        .output(wav_file_path[:-4] + "." + format_to_convert_to)
                                    )
                                    ffmpeg.execute()
                                    os.remove(wav_file_path)
                        elif (stream_name.endswith(".ivf")):
                            ivf_name = base_cutscene_name + ".ivf"
                            ivf_path = cutscene_dir + "/" + ivf_name
                            with open(ivf_path, "wb") as file:
                                file.write(demux[stream_name])
                            if (convert_to_video_index != None):
                                ffmpeg = (
                                    FFmpeg()
                                    .option("y")
                                    .input(ivf_path)
                                    .output(ivf_path[:-4] + "." + sys.argv[convert_to_video_index + 1])
                                )
                                ffmpeg.execute()

                                os.makedirs(cutscene_dir + "/unconverted", exist_ok=True)
                                os.rename(ivf_path, cutscene_dir + "/unconverted/" + ivf_name)
                        else:
                            print("   Unknown file type: " + stream_name + ".")

                    print("Successfully extracted " + cutscene_name)
                else:
                    print("File not found: " + usm_path)       
        elif (sys.argv[1] == "export"): # TODO: Yet again python file handling takes forever
            if (len(sys.argv) <= 2):
                print("Not enough arguments!")
                print_help()
                return

            shutil.make_archive(sys.argv[2], 'zip', sys.argv[2])
            os.rename(sys.argv[2] + ".zip", sys.argv[2] + "." + get_mod_game(sys.argv[2]) + "cr")

            print("Exported to " + sys.argv[2] + "." + get_mod_game(sys.argv[2]) + "cr.")
        elif (sys.argv[1] == "apply"):
            if (len(sys.argv) <= 2):
                print("Not enough arguments!")
                print_help()
                return

            try:
                shutil.rmtree(".temp")
            except:
                pass
            os.mkdir(".temp")
            mod_dir = sys.argv[2]

            if (os.path.isfile(sys.argv[2])):
                with zipfile.ZipFile(sys.argv[2], 'r') as xxcr_file:
                    xxcr_file.extractall(".temp")
                mod_dir = ".temp"
                print("Unzipped the zip.")
            elif (not os.path.isdir(sys.argv[2])):
                raise Exception('Mod file or dir does not exist!')

            game = get_mod_game(mod_dir)
            path_to_video_assets_dir = get_mod_game_video_assets_location(mod_dir)

            for directory, _, files in os.walk(mod_dir):
                if (directory == mod_dir or len(files) == 0):
                    continue
                dir_path_objective = directory[len(mod_dir)+1:]
                dir_name = os.path.basename(directory)
                path_to_target_usm = path_to_video_assets_dir + "/" + dir_path_objective + ".usm"
                if (not os.path.isfile(path_to_target_usm)):
                    raise Exception(path_to_target_usm + " not found!")
            
                print("Changing cutscene: " + dir_path_objective)
                path_to_target_usm_persistent = path_to_target_usm.replace("StreamingAssets", "Persistent")
                usm_key = usm.recover_key(path_to_target_usm).candidates[0].key
                print('   Found key: {:X}'.format(usm_key))

                base_mod_file_path = directory + "/" + dir_name
                video_path = base_mod_file_path + ".ivf"
                if (not os.path.isfile(video_path)):
                    raise Exception('No video path found!')

                if (game == "gi" or game == "sr"):
                    extension = "hca" if (game == "gi") else "adx"

                    audio_a = base_mod_file_path + "." + extension
                    audio_paths = [audio_a, audio_a, audio_a, audio_a]
                    if (os.path.isfile(base_mod_file_path + "-CN." + extension)):
                        audio_paths[0] = base_mod_file_path + "-CN." + extension
                    if (os.path.isfile(base_mod_file_path + "-EN." + extension)):
                        audio_paths[1] = base_mod_file_path + "-EN." + extension
                    if (os.path.isfile(base_mod_file_path + "-JP." + extension)):
                        audio_paths[2] = base_mod_file_path + "-JP." + extension
                    if (os.path.isfile(base_mod_file_path + "-KR." + extension)):
                        audio_paths[3] = base_mod_file_path + "-KR." + extension

                    for i, audio_path in enumerate(audio_paths):
                        if (not (os.path.isfile(audio_path))):
                            lang_list = ["CN", "EN", "JP", "KR"]
                            raise Exception('No sound path found for language ' + lang_list[i] + '!')
                elif (game == "zz"):
                    audio_paths = []

                os.makedirs(os.path.dirname(path_to_target_usm_persistent), exist_ok=True) # For nested files
                usm.mux_to_file(
                    output_path=path_to_target_usm_persistent,
                    video_path=video_path,
                    audio_paths=audio_paths,
                    encrypt_audio=False,
                    key=usm_key,
                )
                print('   Replaced ' + path_to_target_usm_persistent + ".")

            shutil.rmtree(".temp")
        elif (sys.argv[1] == "revert"):
            if (len(sys.argv) <= 2 or not sys.argv[2].lower() in ['gi', 'zz', 'sr']):
                print("Not enough arguments or invalid game!")
                print_help()
                return

            path_to_video_assets_dir = get_config()[game_id_from_name[sys.argv[2].lower()]][:-1]
            persistent_dir = path_to_video_assets_dir.replace("StreamingAssets", "Persistent")

            shutil.rmtree(persistent_dir)
            os.mkdir(persistent_dir)
        elif (sys.argv[1] == "cutscenes"):
            if (len(sys.argv) <= 2 or not sys.argv[2].lower() in ['gi', 'zz', 'sr']):
                print("Not enough arguments or invalid game!")
                print_help()
                return

            path_to_video_assets_dir = get_config()[game_id_from_name[sys.argv[2].lower()]][:-1]

            separator = sys.argv[3] if (len(sys.argv) > 3) else '   '

            cutscene_paths = [y for x in os.walk(path_to_video_assets_dir) for y in glob(os.path.join(x[0], '*.usm'))]
            cutscenes = []
            for cutscene in cutscene_paths:
                cutscenes += [cutscene[:-4][len(path_to_video_assets_dir):]]
            print(separator.join(cutscenes))
        else:
            print_help()

if (sys.argv[0] == "XXCR.py"):
    main()