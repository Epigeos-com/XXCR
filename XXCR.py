from cricodecs import hca, usm
import sys
import os
from datetime import datetime, timezone
import shutil
from ffmpeg import FFmpeg
from pathlib import Path
import zipfile
import io

# TODO: Make the backup optional or partial?

def print_help():
    print("\nUsage:")
    print("\n   XXCR.py config")
    print("\n   XXCR.py apply <mod_dir_or_zip>")
    print("      NOTE: The first apply will backup all cutscenes.")
    print("\n   XXCR.py revert (GI|ZZ|SR) (--delete-backup)")
    print("      NOTE: Reverts all mods.")
    print("\n   XXCR.py create <mod_name> (GI|ZZ|SR)")
    print("\n   XXCR.py file <mod_name> <cutscene_name> (-v <video_file>) (-cn <audio_file>) (-en <audio_file>) (-jp <audio_file>) (-kr <audio_file>) (-a <audio_file>)")
    print("      NOTE: Pass 'r' instead of a file path to remove the file")
    print("      NOTE: Any file format that can be converted by ffmpeg into ivf for video or wav for audio is supported.")
    print("      NOTE: Files that have a very different resolution than the original may break.")
    print("      NOTE: Files passed with -a are treated as a kind of default, the language-specific choices override it.")
    print("\n   XXCR.py compress <mod_name>")
    print("      NOTE: This does not differ from compressing the mod folder into a zip file by other means")

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
def get_mod_video_file_location(mod):
    return get_config()[game_id_from_name[get_mod_game(mod)]][:-1]

def cp(src, dst): # Idk, I copied this from somewhere cuz it was supposed to be faster than the vanilla thing, but it's still horribly slow # TODO
    with open(src, 'rb') as fin:
        with open(dst, 'wb') as fout:
            shutil.copyfileobj(fin, fout, 128*1024)

def main():
    if (len(sys.argv) == 1):
        print_help()
    else:
        if (sys.argv[1] == "config"):
            for game, location in [["GI", ".../GenshinImpact_Data/StreamingAssets/VideoAssets/StandaloneWindows64/"], ["ZZ", "???"], ["SR", "???"]]:
                while True:
                    print("\n      NOTE: Should be at `" + location + "`")
                    print("      NOTE: Leave empty if you're not gonna be modifying " + game)
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

            cutscene_name = sys.argv[3]

            if (not os.path.isdir(sys.argv[2])):
                raise Exception('Mod directory `' + sys.argv[2] + '` does not exist. Use XXCR.py create first.' )
            os.makedirs(sys.argv[2] + "/" + cutscene_name, exist_ok=True)

            path_to_video_assets_dir = get_mod_video_file_location(sys.argv[2])
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
                match arg:
                    case "-v":
                        target_file_name = cutscene_name + ".ivf"
                    case "-cn":
                        target_file_name = cutscene_name + "-CN.hca"
                    case "-en":
                        target_file_name = cutscene_name + "-EN.hca"
                    case "-jp":
                        target_file_name = cutscene_name + "-JP.hca"
                    case "-kr":
                        target_file_name = cutscene_name + "-KR.hca"
                    case "-a":
                        target_file_name = cutscene_name + ".hca"
                split_original = os.path.splitext(file)
                split_target = os.path.splitext(target_file_name)
                
                path_to_final_target_file = sys.argv[2] + "/" + cutscene_name + "/" + target_file_name
                if (file == "r" or os.path.isfile(path_to_final_target_file)):
                    print("Removing from the local file and fixing symlinks.")
                    original_symlink_file = "" # This is the original unconverted file, e.g. webm or wav
                    with open(".local-" + sys.argv[2], "w") as local_file_write:
                        for i in range(round(len(local_file_read)/2)):
                            if (local_file_read[2*i + 1] != path_to_final_target_file + "\n"):
                                local_file_write.write(local_file_read[2*i] + local_file_read[2*i + 1])
                            else:
                                original_symlink_file = local_file_read[2*i][:-1]
                                
                    new_symlink_target = ""
                    try:
                        with open(sys.argv[2] + "/.symlinks", "r") as symlinks_file:
                            symlinks_file_read = symlinks_file.readlines()
                    except:
                        symlinks_file_read = ""
                    with open(sys.argv[2] + "/.symlinks", "w+") as symlinks_file:
                        for i in range(round(len(symlinks_file_read)/2)):
                            if (symlinks_file_read[2*i + 1] == path_to_final_target_file + "\n"): # Does something symlink to the soon to be deleted file
                                if (new_symlink_target == ""):
                                    new_symlink_target = symlinks_file_read[2*i][:-1]
                                    os.remove(new_symlink_target)
                                    cp(path_to_final_target_file, new_symlink_target)
                                    if (original_symlink_file != ""):
                                        with open(".local-" + sys.argv[2], "a") as local_file_append:
                                            local_file_append.write(original_symlink_file + "\n" + new_symlink_target + "\n")
                                else:
                                    symlinks_file.write(symlinks_file_read[2*i] + new_symlink_target + "\n")
                                    os.remove(symlinks_file_read[2*i][:-1])
                                    os.symlink(new_symlink_target, symlinks_file_read[2*i][:-1])
                            else:
                                if (symlinks_file_read[2*i] != path_to_final_target_file + "\n"): # Is the soon to be deleted file not a symlink
                                    symlinks_file.write(symlinks_file_read[2*i] + symlinks_file_read[2*i + 1])
                
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
                    print(file + " was already used for " + path + ". Creating symlink. Adding to .symlinks, which will ensure that if the original file is removed the symlinks will be changed accordingly.")
                    os.symlink(path, path_to_final_target_file)
                    with open(sys.argv[2] + "/.symlinks", "a") as symlinks_file:
                        symlinks_file.write(path_to_final_target_file + "\n" + path + "\n")
                else:
                    if (split_target[1] == split_original[1]):
                        cp(file, sys.argv[2] + "/.temp/" + target_file_name)
                    else:
                        if (arg == "-v"):
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
                                ffmpeg = (
                                    FFmpeg()
                                    .option("y")
                                    .input(file)
                                    .output(wav_path)
                                )
                                ffmpeg.execute()
                            
                            hca_config = hca.HcaEncodeConfig()
                            hca_config.sample_rate = 48_000
                            hca_config.channel_count = 2
                            hca_config.quality = hca.HcaQuality.HIGH
                            hca_bytes = hca.encode(Path(wav_path).read_bytes(), hca_config)
                            Path(sys.argv[2] + "/.temp/" + target_file_name).write_bytes(hca_bytes)

                            os.remove(wav_path)

                    src_path = sys.argv[2] + "/.temp/" + target_file_name
                    dst_path = sys.argv[2] + "/" + cutscene_name + "/" + target_file_name
                    cp(src_path, dst_path)
                    os.remove(src_path)

                    with open(".local-" + sys.argv[2], "a") as local_file_append:
                        local_file_append.write(file + "\n" + path_to_final_target_file + "\n")
                

            shutil.rmtree(sys.argv[2] + "/.temp")
        elif (sys.argv[1] == "compress"):
            if (len(sys.argv) <= 2):
                print("Not enough arguments!")
                print_help()
                return

            shutil.make_archive(sys.argv[2], 'zip', sys.argv[2])
            os.rename(sys.argv[2] + ".zip", sys.argv[2] + "." + get_mod_game(sys.argv[2]) + "cr")

            print("Compressed to " + sys.argv[2] + "." + get_mod_game(sys.argv[2]) + "cr.")
        elif (sys.argv[1] == "apply"):
            if (len(sys.argv) <= 2):
                print("Not enough arguments!")
                print_help()
                return

            try:
                shutil.rmtree(".temp")
            except:
                pass
            os.makedirs(".temp/usm")
            mod_dir = sys.argv[2]

            path_to_video_assets_dir = get_mod_video_file_location(mod_dir)

            if (os.path.isfile(sys.argv[2])):
                if (sys.argv[2].endswith("." + get_mod_game(sys.argv[2]) + "cr")):
                    with zipfile.ZipFile(path_to_zip_file, 'r') as gicr_file:
                        gicr_file.extractall(".temp/extracted")
                        mod_dir = ".temp"
                        print("Unzipped the zip.")
                else:
                    raise Exception('Invalid file! Expected extension: ' + sys.argv[2].endswith("." + get_mod_game(sys.argv[2]) + "cr"))
            elif (not os.path.isdir(sys.argv[2])):
                raise Exception('Mod file or dir does not exist!')

            for f in os.scandir(mod_dir):
                if f.is_dir():
                    print("Changing cutscene: " + f.name)
                    path_to_target_usm = path_to_video_assets_dir + "/" + f.name + ".usm"
                    if (not os.path.isfile(path_to_target_usm)):
                        raise Exception(path_to_target_usm + " not found!")
                    usm_key = usm.recover_key(path_to_target_usm).candidates[0].key
                    print('   Found key: {:X}'.format(usm_key))

                    base_file_path = f.path + "/" + f.name
                    video_path = base_file_path + ".ivf"
                    audio_paths = [base_file_path + ".hca", base_file_path + ".hca", base_file_path + ".hca", base_file_path + ".hca"]
                    if (os.path.isfile(base_file_path + "-CN.hca")):
                        audio_paths[0] = base_file_path + "-CN.hca"
                    if (os.path.isfile(base_file_path + "-EN.hca")):
                        audio_paths[0] = base_file_path + "-EN.hca"
                    if (os.path.isfile(base_file_path + "-JP.hca")):
                        audio_paths[0] = base_file_path + "-JP.hca"
                    if (os.path.isfile(base_file_path + "-KR.hca")):
                        audio_paths[0] = base_file_path + "-KR.hca"

                    for i, audio_path in enumerate(audio_paths):
                        if (not os.path.isfile(audio_path)):
                            lang_dict = {0: "CN", 1: "EN", 2: "JP", 3: "KR"}
                            raise Exception('No sound path found for language ' + lang_dict[i] + '!')

                    usm.mux_to_file(
                        output_path=".temp/usm/"+f.name+".usm",
                        video_path=video_path,
                        audio_paths=audio_paths,
                        encrypt_audio=False,
                        key=usm_key,
                    )

            src_dir = path_to_video_assets_dir
            dst_dir = path_to_video_assets_dir + "/originals"
            try:
                os.mkdir(dst_dir)
                print('Creating backup at ' + dst_dir + '.')
                all_files = os.listdir(src_dir)
                for file in all_files:
                    src_path = src_dir + "/" + file
                    dst_path = dst_dir + "/" + file
                    cp(src_path, dst_path)
            except:
                print('Backup already exists or an error occured.')

            src_dir = ".temp/usm/"
            dst_dir = path_to_video_assets_dir
            all_files = os.listdir(src_dir)
            for file in all_files:
                src_path = src_dir + "/" + file
                dst_path = dst_dir + "/" + file
                cp(src_path, dst_path)
                print('   Replaced ' + dst_path + ".")

            shutil.rmtree(".temp")
        elif (sys.argv[1] == "revert"):
            if (len(sys.argv) <= 2 or not sys.argv[2].lower() in ['gi', 'zz', 'sr']):
                print("Not enough arguments or invalid game!")
                print_help()
                return

            path_to_video_assets_dir = get_config()[game_id_from_name[sys.argv[2].lower()]][:-1]

            remove_backup = len(sys.argv) > 3 and sys.argv[3] == "--delete-backup"
            src_dir = path_to_video_assets_dir + "/originals"
            dst_dir = path_to_video_assets_dir
            all_files = os.listdir(src_dir)
            for file in all_files:
                src_path = src_dir + "/" + file
                dst_path = dst_dir + "/" + file
                cp(src_path, dst_path)
                print("  Reverted " + dst_path + ".")
            if (remove_backup):
                os.rmtree(src_dir)
        else:
            print_help()

main()