import paramiko
import os

plaintext_ssh_user = "opensylar"
plaintext_ssh_password = "pxgtsjmnt"
serv_lst = "srv.txt"

yum_cmd = 'yum list installed'
file_name_yum_append = "-yum-list"

rpm_cmd = 'rpm -qa --qf "%{INSTALLTIME:date} %{NAME}-%{VERSION}-%{RELEASE}\n"'
file_name_append = "-rpm-qa"
file_name_rpm_append = "-rpm-qa"

pip_cmd = 'pip3 freeze'
file_name_pip_freeze_append = "-pip3-freeze"
file_local_compare = "diff-lists\\pip-freeze.lst"


def conn_ssh(ip, username, ssh_pass, remote_cmd):
    s = paramiko.SSHClient()
    s.load_system_host_keys()
    s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    s.connect(ip, 22, username, ssh_pass)
    stdin, stdout, stderr = s.exec_command(remote_cmd)

    stdout = stdout.readlines()
    stderr = stderr.readlines()

    str_output = ''.join(str(e) for e in stdout)
    str_err_output = ''.join(str(e) for e in stderr)

    ret = {"stdout": str_output, "stderr": str_err_output}
    s.close()
    return ret


def main():
    u = util.Util()
    a = app.App()
    creds_b64 = a.get_creds("creds.json")
    plaintext_sudo_password = u.b64_decrypt(creds_b64["sudo_password"])
    plaintext_ssh_user = u.b64_decrypt(creds_b64["ssh_user"])
    plaintext_ssh_password = u.b64_decrypt(creds_b64["ssh_password"])
    all_cmds = a.get_array_cmd("cmds.json", plaintext_sudo_password)


    # Open IP file
    with open(serv_lst, "r") as f:
        text = f.readlines()

    # for-loop for IP list
    for lineHost in text:
        lineHost = lineHost.replace("\n", "")

        # Connect SSH
        print("[+]Connecting Addr::" + lineHost)

        for c_cmd in all_cmds:
            ret = conn_ssh(lineHost, plaintext_ssh_user, plaintext_ssh_password, c_cmd)

            with open("log.log", "a", encoding="utf-8") as fp:
                all_output = ret["stdout"] + ret["stderr"]
                fp.write(all_output)
                fp.close()

        print("SOC Output Results")


def exec_and_log(hst, usr, pwd, cmd, append_file_name):
    return_data = conn_ssh(hst, usr, pwd, cmd)

    file_path = "logs/" + hst + "-" + append_file_name + ".log"
    with open(file_path, "w") as fp:
        fp.write(return_data["stdout"])
        fp.close()


def parse_rpm(hst, usr, pwd, cmd, append_file_name):
    return_data = conn_ssh(hst, usr, pwd, cmd)
    split_lines = return_data["stdout"].split("\n")

    file_path = "logs/" + hst + append_file_name + ".log"
    with open(file_path, "w") as fp:
        fp.write(return_data["stdout"])
        fp.close()

    for one_line in split_lines:
        if len(one_line) > 3:
            split_space = one_line.split(" ")
            end_date = (len(split_space)-1)
            split_dash = one_line.split("-")

            if len(split_dash) == 0x3:
                package_name = split_dash[0x0]
                package_version = split_dash[0x1]
                package_arch = split_dash[0x2]
                # print(package_name)

            else:
                len_package_name = len(split_dash) - 3
                package_name = ""

                for indx in range(len_package_name):
                    if (indx+1) == len_package_name:
                        package_name += split_dash[indx]
                    else:
                        package_name += split_dash[indx] + "-"

                package_version = split_dash[-2]
                package_arch = split_dash[-1]
                # print(package_name)


def parse_pip(hst, usr, pwd, cmd, file_compare, append_file_name):

    if os.path.isfile(file_compare) is False:
        print("[!] " + file_compare + " not exists, pip compare unvailable!")
        return None

    local_packages_list = []
    total_missing_packages = []
    total_upgrades_packages = []

    with open(file_compare, "r", encoding="utf-16") as fp_in:
        for one_line_local_file in fp_in.readlines():
            one_line_local_file = one_line_local_file.replace("\n", "")
            equal_split = one_line_local_file.split("==")
            local_packages_list.append({"name": equal_split[0x0], "version": equal_split[0x1]})

        return_data = conn_ssh(hst, usr, pwd, cmd)
        split_lines = return_data["stdout"].split("\n")

        file_path = "logs/" + hst + append_file_name + ".log"
        with open(file_path, "w", encoding="utf-8") as fp_out:
            fp_out.write(return_data["stdout"])
            fp_out.close()

        # iter local packages
        for one_local_package in local_packages_list:
            missing_package = True

            # iter remote packages
            for one_line in split_lines:
                if len(one_line) > 3:
                    equal_split = one_line.split("==")
                    one_remote_package = {"name": equal_split[0x0], "version": equal_split[0x1]}

                    if one_local_package["name"] == one_remote_package["name"]:
                        missing_package = False
                        version_int_local = int(one_local_package["version"].replace(".", ""))
                        version_int_remote = int(one_remote_package["version"].replace(".", ""))

                        if version_int_local > version_int_remote:
                            total_upgrades_packages.append({"name": one_local_package["name"], "version": one_local_package["version"]})
                            print("[+] Need upgrade " + one_local_package["name"] + " from " + one_remote_package["version"] + " to " + one_local_package["version"])

            if missing_package:
                total_missing_packages.append(one_local_package["name"])
                print("[+] Package missing " + one_local_package["name"])

    return {"upgrades": total_upgrades_packages, "missing": total_missing_packages}


def gen_pip_command(data):
    install_cmd = "pip3 install "

    for one_line in data["missing"]:
        install_cmd += one_line + " "

    install_cmd += one_line + ";pip3 install "

    for one_line in data["upgrades"]:
        install_cmd += one_line["name"] + "==" + one_line["version"] + " "

    return install_cmd


def parse_yum(hst, usr, pwd, cmd, append_file_name):
    return_data = conn_ssh(hst, usr, pwd, cmd)
    split_lines = return_data["stdout"].split("\n")

    file_path = "logs/" + hst + append_file_name + ".log"
    with open(file_path, "w") as fp:
        fp.write(return_data["stdout"])
        fp.close()

    for one_line in split_lines:
        yum_packages = one_line.split()

        if len(yum_packages) == 0x3:
            package_name = yum_packages[0x0]
            package_version = yum_packages[0x1]
            print(package_name)


# Open IP file
with open(serv_lst, "r") as f:
    text = f.readlines()

    # for-loop for IP list
    for host in text:
        host = host.replace("\n", "")

        print("[+] Exec RPM cmd over " + host)
        parse_rpm(host, plaintext_ssh_user, plaintext_ssh_password, rpm_cmd, file_name_rpm_append)

        print("[+] Exec pip freeze over " + host)
        list_pip_packages = parse_pip(host, plaintext_ssh_user, plaintext_ssh_password, pip_cmd, file_local_compare, file_name_pip_freeze_append)

        if list_pip_packages is not None:
            pip_install_cmd = gen_pip_command(list_pip_packages)
            file_name_pip_install_append = "-pip3-install"
            print("[+] Exec pip install cmd over " + host)
            exec_and_log(host, plaintext_ssh_user, plaintext_ssh_password, pip_install_cmd, file_name_pip_install_append)

        # parse_yum(host, plaintext_ssh_user, plaintext_ssh_password, c_cmd, file_name_append)