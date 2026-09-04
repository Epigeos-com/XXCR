from cricodecs import hca, adx, usm
from ffmpeg import FFmpeg
import sys
import os
import shutil
import io
import zipfile
import subprocess
import platform
from glob import glob
from datetime import datetime, timezone
import json

# TODO: Separate enabling/disabling mods from applying/reverting
# TODO: Make a command or automatically do on export clean unused files

def print_help():
    print("\nUsage:")
    print("\n  Basic:")
    print("\n      XXCR.py help")
    print("\n      XXCR.py config")
    print("\n\n  Application:")
    print("\n      XXCR.py apply <mod_dir_or_file>")
    print("\n      XXCR.py revert (GI|ZZ|SR)")
    print("\n\n  Creation:")
    print("\n      XXCR.py create (GI|ZZ|SR) <mod_name> <author> <description>")
    print("\n      XXCR.py export <mod_name>")
    print("\n      XXCR.py files <mod_name> (remove) (-v <video_files>) (-a <audio_files>)")
    print("         NOTE: Any file format that can be converted by ffmpeg into ivf for video or wav for audio is supported.")
    print("\n      XXCR.py replace-cutscenes <mod_name> <comma_separated_cutscene_names> (<video_file>) (-cn <audio_file>) (-en <audio_file>) (-jp <audio_file>) (-kr <audio_file>) (-a <audio_file>)")
    print("         NOTE: Add files with `XXCR.py files` first.")
    print("         NOTE: To revert a cutscene modification, simply run this without providing any files.")
    print("         NOTE: Files that have a very different resolution than the original may break.")
    print("         NOTE: Files passed with -a are treated as a kind of default, the language-specific choices override them.")
    print("         NOTE: You can also provide `all` instead of a cutscene name to set a default for all cutscenes.")
    print("\n      XXCR.py replace-cutscenes-script <mod_name> <comma_separated_cutscene_names> (<script_name>)")
    print("         NOTE: If it doesn't yet exist, this will create a new script inside the mod folder, please edit it there.")
    print("         NOTE: You can also provide `all` instead of a cutscene name to set a default for all cutscenes.")
    print("\n\n  Extraction:")
    print("\n      XXCR.py list-cutscenes (GI|ZZ|SR) (<separator>)")
    print("\n      XXCR.py extract-cutscenes (GI|ZZ|SR) <comma_separated_cutscene_names> (-cv <target_video_format>) (-ca <target_audio_format>)")

version = "1.0.3"
supported_games = ["gi", "zz", "sr"]
def get_config():
    try:
        with open("config.txt", "r") as file:
            return file.readlines()
    except:
        raise Exception('Please run `XXCR.py config` first.')
def get_mod_metadata(mod_name):
    try:
        with open(mod_name + "/metadata.json", "r") as file:
            return json.loads(file.read())
    except:
        raise Exception('No metadata.json found at ./' + mod_name + "/")
def get_file_extension(is_video, game):
    if (is_video):
        return ".ivf"
    else:
        match game:
            case "gi":
                return ".hca"
            case "zz":
                raise Exception('For ZZZ only video is available as audio is stored separately - use XXAR for audio instead.')
            case "sr":
                return ".adx"
def remove_trailing_slash(text):
    if (text.endswith("/") or text.endswith("\\")):
        text = text[:-1]
    return text
def recover_key(source, file_type_class):
    key = file_type_class.recover_key(source).candidates[0].key
    print('   Found key: {:X}'.format(key))
    return key
def cp(src, dst):
    if (platform.system() == "Linux"):
        subprocess.run(['cp', src, dst]) # This is a lot faster
    else:
        shutil.copy(src, dst)

def main():
    if (len(sys.argv) == 1):
        print_help()
    else:
        if (sys.argv[1] == "config"):
            for game, location, windows_specific_location in [["GI", "/path/to/GenshinImpact_Data/StreamingAssets/VideoAssets/StandaloneWindows64/", "C:/Program Files/Genshin Impact/Genshin Impact Game"], ["ZZ", "/path/to/ZenlessZoneZero_Data/StreamingAssets/Video/HD/", "C:/Program Files/Zenless Zone Zero/Zenless Zone Zero Game"], ["SR", "/path/to/StarRail_Data/StreamingAssets/Video/Windows/", "C:/Program Files/HoYoPlay/games/Star Rail Games"]]:
                if (platform.system() == "Windows"):
                    location = windows_specific_location + location[8:]
                while True:
                    print("\n   NOTE: Should be at `" + location + "` and should contain .usm files")
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
                    with open("config.txt", "w") as file:
                        file.write(directory + "\n")
                    break
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

            mod_metadata = get_mod_metadata(mod_dir)
            game = mod_metadata["game"]
            path_to_video_assets_dir = get_config()[supported_games.index(game)][:-1]

            has_accepted_script_mod = False

            cutscenes = [*mod_metadata["replacements"]]
            uses_all_cutscene = False
            uses_all_cutscene_from_index = -1
            if ("all" in cutscenes):
                cutscenes.remove("all")
                uses_all_cutscene = True
                uses_all_cutscene_from_index = len(cutscenes) - 1
                all_available_cutscene_paths = [y for x in os.walk(path_to_video_assets_dir) for y in glob(os.path.join(x[0], '*.usm'))]
                for available_cutscene_path in all_available_cutscene_paths:
                    available_cutscene = available_cutscene_path[:-4][len(path_to_video_assets_dir):]
                    if (not available_cutscene in cutscenes):
                        cutscenes += [available_cutscene]

            if (len(cutscenes) == 0):
                if (uses_all_cutscene):
                    raise Exception('No available cutscenes, make sure the path set during config is correct')
                else:
                    raise Exception('Mod isn\'t set to modify any cutscenes')

            for i, cutscene in enumerate(cutscenes):
                cutscene_name_in_metadata = "all" if (uses_all_cutscene and i > uses_all_cutscene_from_index) else cutscene
                path_to_target_usm = path_to_video_assets_dir + "/" + cutscene + ".usm"
                if (not os.path.isfile(path_to_target_usm)):
                    raise Exception(path_to_target_usm + " not found!")
                print("Changing cutscene: " + cutscene)

                path_to_target_usm_persistent = path_to_target_usm.replace("StreamingAssets", "Persistent")
                usm_key = recover_key(path_to_target_usm, usm)
                usm_load = usm.load(path_to_target_usm, key=usm_key)

                encrypt_audio = False
                for i in range(usm_load.stream_count):
                    stream = usm_load.stream(i)
                    if (stream.stream_id == usm.UsmChunkType.SFA):
                        file_bytes = usm_load.stream_bytes(i)
                        sound_file_type_class = hca if (game == "gi") else adx
                        try:
                            recover_key(file_bytes, sound_file_type_class)
                            print("   Original sound files seem to be encrypted, will encrypt target sounds as well.")
                            encrypt_audio = True
                        except:
                            pass
                        break
                    

                if (has_accepted_script_mod == False and mod_metadata["replacements"][cutscene_name_in_metadata]["type"] == "script"):
                    while True:
                        agreement = input("   This mod uses scripts to procedurally replace cutscenes. That means it can run its own code, which could potentially be malicious, please look over the code before running. Do you wish to proceed? [y/n]: ")
                        if (agreement.lower() == "y"):
                            has_accepted_script_mod = True
                            break
                        elif (agreement.lower() == "n"):
                            raise Exception("Canceled by user.")
                        else:
                            print("   Please answer 'y' or 'n'.")
                            continue

                if (mod_metadata["replacements"][cutscene_name_in_metadata]["type"] == "replace"):
                    video_path = mod_dir + "/" + mod_metadata["replacements"][cutscene_name_in_metadata]["files"]["v"]
                    if (not os.path.isfile(video_path)):
                        raise Exception('File ' + video_path + ' not found!')

                    if (game == 'zz'):
                        audio_paths = []
                    else:
                        langs = ["cn", "en", "jp", "kr", "a"]
                        audio_paths = [None, None, None, None, None]
                        for i, lang in enumerate(langs):
                            if (lang in mod_metadata["replacements"][cutscene_name_in_metadata]["files"]):
                                audio_paths[i] = mod_dir + "/" + mod_metadata["replacements"][cutscene_name_in_metadata]["files"][lang]
                                if (not os.path.isfile(audio_paths[i])):
                                    raise Exception('File ' + audio_paths[i] + ' not found!')
                        if (None in audio_paths[:-1]):
                            if (audio_paths[-1] == None):
                                raise Exception("Not all languages have a sound path!")
                            else: # [None, None, None, None, a_file.hca] -> [a_file.hca, a_file.hca, a_file.hca, a_file.hca, a_file.hca]
                                for i in range(len(audio_paths)):
                                    if (audio_paths[i] == None):
                                        audio_paths[i] = audio_paths[-1]
                        audio_paths = audio_paths[:-1]

                    usm_config = usm.UsmMuxConfig
                elif (mod_metadata["replacements"][cutscene_name_in_metadata]["type"] == "script"):
                    script_file = mod_dir + "/" + mod_metadata["replacements"][cutscene_name_in_metadata]["script"]
                    print("   Running mod script `" + script_file + "`.")
                    with open(script_file, "r") as script:
                        code = script.read()
                        script_locals = locals()
                        exec(code, globals(), script_locals)

                        change_cutscene = script_locals['change_cutscene']
                        if (not change_cutscene):
                            print("   Script doesn't want to replace this cutscene. Continuing.")
                            continue
                        video_path = script_locals['video_path']
                        if (game != "zz"):
                            audio_paths = script_locals['audio_paths']
                            if (len(audio_paths) != 4):
                                raise Exception('Invalid audio_paths returned by script: ' + str(audio_paths) + ' - len should be 4: [CN, EN, JP, KR].')
                        elif ('audio_paths' in script_locals):
                            raise Exception('Script wants to change sound for ZZ. This can only be done through XXAR, as ZZ stores sound separately.')
                else:
                    raise Exception('Invalid replacement type: ' + mod_metadata["replacements"][cutscene_name_in_metadata]["type"] + '.')

                os.makedirs(os.path.dirname(path_to_target_usm_persistent), exist_ok=True) # For nested files
                usm.mux_to_file(
                    output_path=path_to_target_usm_persistent,
                    video_path=video_path,
                    audio_paths=audio_paths,
                    encrypt_audio=encrypt_audio,
                    key=usm_key
                )
                print('   Replaced ' + path_to_target_usm_persistent + ".")

            shutil.rmtree(".temp")
        elif (sys.argv[1] == "revert"):
            if (len(sys.argv) <= 2 or not sys.argv[2].lower() in supported_games):
                print("Not enough arguments or invalid game!")
                print_help()
                return

            path_to_video_assets_dir = get_config()[supported_games.index(sys.argv[2].lower())][:-1]
            persistent_dir = path_to_video_assets_dir.replace("StreamingAssets", "Persistent")

            shutil.rmtree(persistent_dir)
            os.mkdir(persistent_dir)
        elif (sys.argv[1] == "create"):
            if (len(sys.argv) <= 5 or not sys.argv[2].lower() in supported_games):
                print("Not enough arguments or invalid game!")
                print_help()
                return

            mod_game = sys.argv[2].lower()
            mod_name = remove_trailing_slash(sys.argv[3])
            author = sys.argv[4]
            description = sys.argv[5]

            os.mkdir(mod_name)
            with open(mod_name + "/metadata.json", "w") as metadata_file:
                metadata_file.write(
                    '{\n'
                    '  "game": "%s",\n'
                    '  "app_version": "%s",\n'
                    '  "name": "%s",\n'
                    '  "author": "%s",\n'
                    '  "description": "%s",\n'
                    '  "created_date": "%s",\n'
                    '  "build_date": "",\n'
                    '  "replacements": {}\n'
                    '}' % (mod_game, version, mod_name, author, description, datetime.now(timezone.utc))
                )

            print("Created mod " + mod_name + " for game " + mod_game.upper() + ".")
        elif (sys.argv[1] == "export"):
            if (len(sys.argv) <= 2):
                print("Not enough arguments!")
                print_help()
                return

            mod_dir = remove_trailing_slash(sys.argv[2])
            mod_metadata = get_mod_metadata(mod_dir)
            game = mod_metadata["game"]

            mod_metadata["build_date"] = str(datetime.now(timezone.utc))
            with open(mod_dir + "/metadata.json", "w") as metadata_file:
                metadata_file.write(json.dumps(mod_metadata, indent=2))
            try:
                shutil.rmtree(mod_dir + "/.temp")
            except:
                pass

            shutil.make_archive(mod_dir, 'zip', mod_dir)
            os.rename(mod_dir + ".zip", mod_dir + "." + game + "cr")

            print("Exported to " + mod_dir + "." + game + "cr.")
        elif (sys.argv[1] == "files"):
            if (len(sys.argv) <= 4):
                print("Not enough arguments!")
                print_help()
                return

            mod_dir = remove_trailing_slash(sys.argv[2])
            game = get_mod_metadata(sys.argv[2])["game"]
            is_remove = sys.argv[3] == "remove"

            if (not os.path.isdir(mod_dir)):
                raise Exception('Mod directory `' + mod_dir + '` does not exist. Use `XXCR.py create` first.' )
            os.makedirs(mod_dir + "/files", exist_ok=True)

            video_arg_index = sys.argv.index("-v") if ("-v" in sys.argv) else None
            audio_arg_index = sys.argv.index("-a") if ("-a" in sys.argv) else None
            if (video_arg_index != None and audio_arg_index != None):
                indices = [[min(video_arg_index, audio_arg_index), max(video_arg_index, audio_arg_index) - 1], [max(video_arg_index, audio_arg_index), len(sys.argv) - 1]]
            elif (video_arg_index != None):
                indices = [[video_arg_index, len(sys.argv) - 1]]
            elif (audio_arg_index != None):
                indices = [[audio_arg_index, len(sys.argv) - 1]]
            else:
                raise Exception("Please provide either -v or -a.")
            for start_i, end_i in indices:
                arg = sys.argv[start_i]
                files = sys.argv[start_i+1:end_i+1]
                extension = get_file_extension(arg == "-v", game)

                if is_remove:
                    for file in files:
                        file_path = mod_dir + "/files/" + file
                        file_path = file_path if (file_path.endswith(extension)) else file_path + extension
                        if (not os.path.isfile(file_path)):
                            raise Exception('File `' + file_path + '` does not exist.' )
                        os.remove(file_path)
                        print("Removed " + file_path + ".")
                else:
                    for file in files:
                        target_file_path = mod_dir + "/files/" + os.path.basename(file) + extension
                        if (os.path.isfile(target_file_path)):
                            raise Exception(target_file_path + " already exits!")
                        if (not os.path.isfile(file)):
                            raise Exception(file + " is not a file!")
                        
                        if (file.endswith(extension)):
                            cp(file, target_file_path)
                        else:
                            if (extension == ".ivf"):
                                print("Converting " + file + " to .ivf with ffmpeg.")
                                ffmpeg = (
                                    FFmpeg()
                                    .option("y")
                                    .input(file)
                                    .output(
                                        target_file_path,
                                        {"codec:v": "libvpx-vp9", "pix_fmt": "yuv420p"}
                                    )
                                )
                                ffmpeg.execute()
                            else:
                                wav_path = target_file_path + ".wav"
                                if (file.endswith(".wav")):
                                    cp(file, wav_path)
                                else:
                                    print("Converting " + file + " to .wav with ffmpeg.")
                                    ffmpeg = (
                                        FFmpeg()
                                        .option("y")
                                        .input(file)
                                        .output(wav_path)
                                    )
                                    ffmpeg.execute()
                                
                                if (extension == ".adx"):
                                    print("Converting " + wav_path + " to .adx with CriCodecs.")
                                    adx_config = adx.AdxEncodeConfig()
                                    adx_config.sample_rate = 48_000
                                    adx_config.channels = 2
                                    adx_config.encoding_mode = 3
                                    adx_config.block_size = 18
                                    adx_config.bit_depth = 4
                                    adx_config.highpass_freq = 500
                                    adx_config.version = 4
                                    with open(wav_path, "rb") as wav_file_rb:
                                        adx_bytes = adx.encode(wav_file_rb.read(), adx_config)
                                    with open(target_file_path, "wb") as target_file_wb:
                                        target_file_wb.write(adx_bytes)
                                else:
                                    print("Converting " + wav_path + " to .hca with CriCodecs.")
                                    hca_config = hca.HcaEncodeConfig()
                                    hca_config.sample_rate = 48_000
                                    hca_config.channel_count = 2
                                    hca_config.quality = hca.HcaQuality.HIGH
                                    with open(wav_path, "rb") as wav_file_rb:
                                        hca_bytes = hca.encode(wav_file_rb.read(), hca_config)
                                    with open(target_file_path, "wb") as target_file_wb:
                                        target_file_wb.write(hca_bytes)

                                os.remove(wav_path)
        elif (sys.argv[1] == "replace-cutscenes"):
            if (len(sys.argv) <= 3):
                print("Not enough arguments!")
                print_help()
                return

            mod_dir = remove_trailing_slash(sys.argv[2])
            if (not os.path.isdir(mod_dir)):
                raise Exception('Mod directory `' + mod_dir + '` does not exist. Use `XXCR.py create` first.' )

            mod_metadata = get_mod_metadata(mod_dir)
            game = mod_metadata["game"]
            path_to_video_assets_dir = get_config()[supported_games.index(game)][:-1]

            for cutscene_name in sys.argv[3].split(','):
                if (len(sys.argv) == 4):
                    print("No files provided, removing modifications for cutscene " + cutscene_name + ".")
                    del mod_metadata["replacements"][cutscene_name]
                    with open(mod_dir + "/metadata.json", "w") as metadata_file:
                        metadata_file.write(json.dumps(mod_metadata, indent=2))
                    continue

                if (not (cutscene_name == "all" or os.path.isfile(path_to_video_assets_dir + "/" + cutscene_name + ".usm"))):
                    raise Exception("Cutscene " + path_to_video_assets_dir + "/" + cutscene_name + ".usm not found.")

                video_extension = get_file_extension(True, game)
                video_file = sys.argv[4] if (sys.argv[4].endswith(video_extension)) else sys.argv[4] + video_extension
                if (not os.path.isfile(mod_dir + "/files/" + video_file)):
                    raise Exception("Video file " + mod_dir + "/files/" + video_file + " not found. Use `XXCR.py files` first.")

                mod_metadata["replacements"].update(
                    {
                        cutscene_name: {
                            "type": "replace",
                            "files": {
                                "v": "files/" + video_file
                            }
                        }
                    }
                )

                if (game != "zz"):
                    audio_extension = get_file_extension(False, game)
                    are_all_audio_files_so_far_provided = True
                    for arg in ["-cn", "-en", "-jp", "-kr", "-a"]:
                        if (arg in sys.argv):
                            audio_file = sys.argv[sys.argv.index(arg) + 1]
                            audio_file = audio_file if (audio_file.endswith(audio_extension)) else audio_file + audio_extension
                            if (not os.path.isfile(mod_dir + "/files/" + audio_file)):
                                raise Exception("Audio file " + mod_dir + "/files/" + audio_file + " not found. Use `XXCR.py files` first.")
                            mod_metadata["replacements"][cutscene_name]["files"].update({arg[1:]: "files/" + audio_file})
                        else:
                            if (arg == "-a" and not are_all_audio_files_so_far_provided):
                                raise Exception("Not all languages have a sound path. Use -a to provide a default for all langauges.")
                            are_all_audio_files_so_far_provided = False
                elif (len(sys.argv) > 5 and sys.argv[5] in ["-cn", "-en", "-jp", "-kr", "-a"]):
                    raise Exception("ZZ stores sound separately from cutscenes. Use XXAR instead to replace ZZ cutscene sounds.")

                with open(mod_dir + "/metadata.json", "w") as metadata_file:
                    metadata_file.write(json.dumps(mod_metadata, indent=2))
        elif (sys.argv[1] == "replace-cutscenes-script"):
            if (len(sys.argv) <= 3):
                print("Not enough arguments!")
                print_help()
                return

            mod_dir = remove_trailing_slash(sys.argv[2])
            if (not os.path.isdir(mod_dir)):
                raise Exception('Mod directory `' + mod_dir + '` does not exist. Use `XXCR.py create` first.' )

            mod_metadata = get_mod_metadata(mod_dir)
            game = mod_metadata["game"]
            path_to_video_assets_dir = get_config()[supported_games.index(game)][:-1]

            if (len(sys.argv) != 4):
                script_name = sys.argv[4] if (sys.argv[4].endswith(".py")) else sys.argv[4] + ".py"
                script_path_relative_to_mod_dir = script_name

                if (not os.path.isfile(mod_dir + "/" + script_path_relative_to_mod_dir)):
                    with open(mod_dir + "/" + script_path_relative_to_mod_dir, "x") as script_file:
                        script_file.write("# Example mod script: replace all of Genshin's male traveler cutscenes with their female counterparts\n\n# Some available vars: mod_dir, cutscene (name), mod_metadata, path_to_video_assets_dir, path_to_target_usm_persistent, path_to_target_usm, usm_key\n# Some available functions: recover_key(source, file_type_class), get_file_extension(is_video, game)\n# Must be set: change_cutscene, if that's True also video_path and for GI and HSR audio_paths (audio_paths in the order CN, EN, JP, KR)\n\nif (cutscene.endswith('Boy')):\n    change_cutscene = True\n    \n    audio_paths = [None, None, None, None]\n    replacement_usm_path = path_to_target_usm[:-7] + 'Girl.usm' # Get and load the Girl version\n    usm_key = recover_key(replacement_usm_path, usm)\n    usm_load = usm.load(replacement_usm_path, key=usm_key)\n\n    try:\n        shutil.rmtree(mod_dir + '/.temp')\n    except:\n        pass\n\n    try:\n        os.mkdir(mod_dir + '/.temp')\n    except:\n        pass\n\n    hca_key = None\n    for i in range(usm_load.stream_count):\n        stream = usm_load.stream(i)\n        file_bytes = usm_load.stream_bytes(i)\n        stream_filename = os.path.basename(stream.filename)\n        if (stream.stream_id == usm.UsmChunkType.SFA):\n            \n            stream_filename = stream_filename if (stream_filename != '') else 'sfa_ch' + str(stream.channel_no)\n            file_path = mod_dir + '/.temp/' + stream_filename\n\n            audio_paths[stream.channel_no] = file_path\n\n            if (hca_key == None):\n                try:\n                    hca_key = recover_key(file_bytes, hca) # HSR would use ADX instead of HCA\n                except:\n                    pass\n            if (hca_key != None):\n                file_bytes = hca.decrypt(file_bytes, keycode=hca_key)\n\n            with open(file_path, 'wb') as file:\n                file.write(file_bytes)\n        elif (stream.stream_id == usm.UsmChunkType.SFV):\n            stream_filename = stream_filename if (stream_filename != '') else 'sfv_ch' + str(stream.channel_no)\n            file_path = mod_dir + '/.temp/' + stream_filename\n\n            video_path = file_path\n\n            with open(file_path, 'wb') as file:\n                file.write(file_bytes)\nelse:\n    change_cutscene = False")


            for cutscene_name in sys.argv[3].split(','):
                if (len(sys.argv) == 4):
                    print("No script name provided, removing modifications for cutscene " + cutscene_name + ".")
                    del mod_metadata["replacements"][cutscene_name]
                    with open(mod_dir + "/metadata.json", "w") as metadata_file:
                        metadata_file.write(json.dumps(mod_metadata, indent=2))
                    continue

                if (not (cutscene_name == "all" or os.path.isfile(path_to_video_assets_dir + "/" + cutscene_name + ".usm"))):
                    raise Exception("Cutscene " + path_to_video_assets_dir + "/" + cutscene_name + ".usm not found.")

                mod_metadata["replacements"].update(
                    {
                        cutscene_name: {
                            "type": "script",
                            "script": script_path_relative_to_mod_dir
                        }
                    }
                )

                with open(mod_dir + "/metadata.json", "w") as metadata_file:
                    metadata_file.write(json.dumps(mod_metadata, indent=2))
        elif (sys.argv[1] == "list-cutscenes"):
            if (len(sys.argv) <= 2 or not sys.argv[2].lower() in supported_games):
                print("Not enough arguments or invalid game!")
                print_help()
                return

            path_to_video_assets_dir = get_config()[supported_games.index(sys.argv[2].lower())][:-1]

            separator = sys.argv[3] if (len(sys.argv) > 3) else '   '

            cutscene_paths = [y for x in os.walk(path_to_video_assets_dir) for y in glob(os.path.join(x[0], '*.usm'))]
            cutscenes = []
            for cutscene in cutscene_paths:
                cutscenes += [cutscene[:-4][len(path_to_video_assets_dir):]]
            print(separator.join(cutscenes))
        elif (sys.argv[1] == "extract-cutscenes"):
            if (len(sys.argv) <= 3 or not sys.argv[2].lower() in supported_games):
                print("Not enough arguments or invalid game!")
                print_help()
                return

            convert_to_video_index = sys.argv.index("-cv") if "-cv" in sys.argv else None
            convert_to_audio_index = sys.argv.index("-ca") if "-ca" in sys.argv else None

            game = sys.argv[2].lower()
            extracted_dir = sys.argv[2].upper() + "_extracted/"
            sound_file_extension = ".hca" if (game == "gi") else ".adx"
            os.makedirs(extracted_dir, exist_ok=True)

            path_to_video_assets_dir = get_config()[supported_games.index(sys.argv[2].lower())][:-1]
            for cutscene_name in sys.argv[3].split(","):
                base_cutscene_name = os.path.basename(cutscene_name)
                usm_path = path_to_video_assets_dir + cutscene_name + ".usm"
                if (os.path.isfile(usm_path)):
                    print("Extracting " + cutscene_name)
                    cutscene_dir = extracted_dir + cutscene_name
                    os.makedirs(cutscene_dir)
                    languages = ["CN", "EN", "JP", "KR"]
                    usm_key = recover_key(usm_path, usm)
                    usm_load = usm.load(usm_path, key=usm_key)
                    for i in range(usm_load.stream_count):
                        stream = usm_load.stream(i)
                        file_bytes = usm_load.stream_bytes(i)
                        if (stream.stream_id == usm.UsmChunkType.SFA): # Audio
                            sound_file_name = base_cutscene_name + "-" + languages[stream.channel_no] + sound_file_extension
                            sound_file_path = cutscene_dir + "/" + sound_file_name
                            with open(sound_file_path, "wb") as file:
                                file.write(file_bytes)
                            if (convert_to_audio_index != None):
                                wav_file_path = sound_file_path[:-4] + ".wav"
                                sound_file_class = hca if (sound_file_extension == ".hca") else adx
                                try:
                                    sound_file_key = recover_key(sound_file_path, sound_file_class)
                                except:
                                    sound_file_key = None
                                with open(wav_file_path, "wb") as file:
                                    if (sound_file_key == None):
                                        file.write(sound_file_class.decode(sound_file_path))
                                    elif (sound_file_extension == ".hca"):
                                        file.write(sound_file_class.decode(sound_file_path, keycode=sound_file_key))
                                    elif (sound_file_extension == ".adx"):
                                        file.write(sound_file_class.decode(sound_file_path, key=sound_file_key))
                                
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
                        elif (stream.stream_id == usm.UsmChunkType.SFV): # Video
                            ivf_name = base_cutscene_name + ".ivf"
                            ivf_path = cutscene_dir + "/" + ivf_name
                            with open(ivf_path, "wb") as file:
                                file.write(file_bytes)
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

                    print("Successfully extracted " + cutscene_name)
                else:
                    print("File not found: " + usm_path)       
        else:
            print_help()

main()