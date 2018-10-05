#! /usr/bin/python3 -u
# -*- coding: utf-8 -*-

import os
import sys
import configparser
import re
import time
import shutil
import random
import pickle
import mmap
import json
import syslog

import requests
import bs4
import telebot
from datetime import date

# pyTelegramBotAPI
# https://github.com/eternnoir/pyTelegramBotAPI
# pip3 install pyTelegramBotAPI


__version__ = "Fri Oct  5 19:10:15 CEST 2018"

START_TIME = time.ctime()


# Message to send to @BotFather about its usage.
Commands_Listing = """

Open a talk to @BotFather and send these commands
using "/setcommands"

== OpenCast bot ==

"""

DEBUG = False
HOME = os.environ.get('HOME')
BOTNAME = "opencastbot"
CONFIG = "%s/.%src" % (HOME, BOTNAME)
PIDFILE = "%s/.%s.pid" % (HOME, BOTNAME)
PAUTAS = "%s/tecnologiaaberta/pautas" % HOME
SCRIPTHOME = "%s/tecnologiaaberta/bot" % HOME
botadms, cfg, key, configuration = None, None, None, None

### Refactoring
# Applying the concepts from clean code (thanks uncle Bob)
def set_debug():
    global DEBUG
    if DEBUG is False:
        if "DEBUG" in os.environ:
            DEBUG = True


def debug(msg):
    if DEBUG and msg:
        try:
            print(u"[%s] %s" % (time.ctime(), msg))
        except Exception as e:
            print(u"[%s] DEBUG ERROR: %s" % (time.ctime(), e))


def error(message):
    """Error handling for logs"""
    errormsg = u"ERROR: %s" % message
    debug(errormsg)
    syslog.openlog(BOTNAME)
    syslog.syslog(syslog.LOG_ERR, errormsg)
    sys.stderr.write(errormsg)


def log(message):
    """Syslog handling for logs"""
    infomsg = u"%s" % message
    debug(infomsg)
    syslog.openlog(BOTNAME)
    syslog.syslog(syslog.LOG_INFO, infomsg)


def read_file(filename):
    try:
        with open(filename) as myfile:
            return myfile.read()
    except FileNotFoundError:
            return None
    except:
        error("Failed to read file %s" % filename)
        return None


def check_if_run():
    pid = read_file(PIDFILE)
    current_pid = os.getpid()
    if pid is None:
        return
    if int(pid) > 0 and int(pid) != current_pid:
        if os.path.exists("/proc/%d" % int(pid)):
            log("[%s] Already running - keepalive done." % time.ctime())
            sys.exit(os.EX_OK)

def save_file(content, filename):
    """Snippet to write down data"""
    with open(filename, 'w') as fd:
        fd.write(content)

def read_configuration(config_file):
    """ Read configuration file and return object
    with config attributes"""
    cfg = configparser.ConfigParser()
    debug("Reading configuration: %s" % config_file)
    if not os.path.exists(config_file):
        error("Failed to find configuration file %s" % config_file)
        sys.exit(os.EX_CONFIG)
    with open(config_file) as fd:
        cfg.read_file(fd)
    return cfg


def get_telegram_key(config_obj, parameter):
    """Read a parameter from configuration object for TELEGRAM
    and return it or exit on failure"""
    debug("get_telegram_key()")
    config_section = "TELEGRAM"
    value = None
    try:
        value = config_obj.get(config_section, parameter)
    except configparser.NoOptionError:
        print("No %s session found to retrieve settings." % config_section)
        print("Check your configuration file.")
        # keep going and just return null
    debug(" * value=%s" % value)
    debug(" * Key acquired (%s=%s)." % (parameter, value) )
    return value


def reply_text(obj, session, text):
    """ Generic interface to answer """
    try:
        obj.reply_to(session, text)
    except Exception as e:
        error("%s" % e)


def StartUp():
    debug("Startup")
    if os.path.exists(SCRIPTHOME):
        os.chdir(SCRIPTHOME)
        oscmd = "git pull -f"
        debug(oscmd)
        os.system(oscmd)
        botname = "%s.py" % BOTNAME
        debug(oscmd)
        # For debugging outside of the Raspberry Pi
        # oscmd = "diff -q %s %s/homemadescripts/%s" % (botname, HOME, botname)
        # Original Raspberry Pi command
        oscmd = "diff -q %s %s/bin/%s" % (botname, HOME, botname)
        res = os.system(oscmd)
        if res:
            # new version detected
            res = os.system("%s %s check" % (sys.executable, sys.argv[0]))
            if res != 0:
                debug("Versão bugada")
                sys.exit(os.EX_OSERR)
            debug("Updating bot...")
            shutil.copy(botname, "%s/bin/%s" % (HOME, botname))
            debug("Bot version updated.")
            # check first
            debug("Calling restart")
            python = sys.executable
            os.execl(python, python, *sys.argv)

def main():
    """Main settings"""
    check_if_run()
    save_file("%d\n" % os.getpid(), PIDFILE)
    StartUp()


def get_global_keys():
    """Read globa settings like telegram key API"""
    debug("get_global_keys()")
    global botadms, key, allowed_users
    cfg = read_configuration(CONFIG)
    key = get_telegram_key(cfg, BOTNAME.upper())
    botadms = get_telegram_key(cfg, "%sADMS" % BOTNAME.upper())
    allowed_users = botadms

# avoiding nulls
set_debug()
debug("Starting %s" % BOTNAME)
get_global_keys()
bot = telebot.TeleBot(key)


### Bot callbacks below ###
@bot.message_handler(commands=["debug"])
def ToggleDebug(cmd):
    global DEBUG
    debug(cmd.text)
    if not cmd.from_user.username in botadms:
        bot.reply_to(cmd, "Só patrão pode isso.")
        return
    try:
        debug(cmd)
        if DEBUG is True:
            DEBUG = False
            status = "disabled"
        elif DEBUG is False:
            DEBUG = True
            status = "enabled"
        bot.reply_to(cmd, "debug=%s" % status)
    except Exception as e:
        print(u"%s" % e)


@bot.message_handler(commands=[
    "pauta",
    "pautas",
    "novapauta",
    "testauser",
    "addsugestao",
    "addnoticias",
    "addliberageral",
    "addobituario",
    "add"
    ])
def PautaHandler(cmd):
    debug("PautaHandler")
    msg = None
    curdir = os.curdir

    def git_init():
        os.chdir(HOME)
        os.system("git clone git@github.com:helioloureiro/tecnologiaaberta.git")

    def get_last_pauta():
        if not os.path.exists(PAUTAS):
            git_init()
        os.chdir(PAUTAS)
        os.system("git pull --rebase --no-commit --force")
        pautas = os.listdir(PAUTAS)
        last_pauta = sorted(pautas)[-1]
        if not re.search("^20", last_pauta):
            last_pauta = sorted(pautas)[-2]
        return last_pauta

    def read_pauta(filename=None):
        if filename is None:
            last_pauta = get_last_pauta()
        else:
            last_pauta = filename
        msg = open("%s/%s" % (PAUTAS, last_pauta)).read()
        return msg

    def sanitize(text):
        REPLACEMENTS = {
            "\(" : "&#40;",
            "\)" : "&#41;",
            "\*" : "&#42;",
            "\<" : "&#60;",
            "\>" : "&#62;",
            "\[" : "&#91;",
            "\]" : "&#93;"
            }
        for pattern in list(REPLACEMENTS):
            text = re.sub(pattern, REPLACEMENTS[pattern], text)
        return text

    def pauta_commit_push(pauta_name, message=None):
        os.chdir(PAUTAS)
        current_time = time.ctime()
        os.system("git add %s" % pauta_name)
        if message is None:
            os.system("git commit -m \"Adding pauta  content at %s\" %s" % (current_time, pauta_name))
        else:
            os.system("git commit -m \"%s\" %s" % (message, pauta_name))
        os.system("git push")


    def add_noticia(command):
        url = command.split()[-1]
        if not re.search("^http", url):
            return
        last_pauta = get_last_pauta()
        pauta_body = read_pauta(last_pauta)

        content = pauta_body.split("\n\n")

        req = requests.get(url)
        html = None
        if req.status_code == 200:
            html = req.text

        if html is not None:
            soup = bs4.BeautifulSoup(html, "html")
            title = sanitize(soup.title.text)
            md_text = "* [%s](%s)" % (title, url)
            content[0] += "\n%s" % md_text
        body = "\n\n".join(content)

        with open(last_pauta, 'w') as fd:
            fd.write(body)
        pauta_commit_push(last_pauta)

    def generate_serial(filename=None):
        if filename is None:
            # generate for next month
            timestamp = str(time.strftime("%Y%m0", time.localtime(time.time() + 30 * 24 * 60 * 60)))
        else:
            time_string = filename.split(".")[0]
            if time_string[0] != 2 or len(time_string) < 7:
                timestap =generate_serial()
            else:
                year = time_string[:4]
                month = time_string[4:6]
                if int(month) == 12:
                    year = str(int(year) + 1)
                    month = "01"
                else:
                    month = "%02d" % (int(month) + 1)
                timestamp = "%s%s" % (year, month)
        return timestamp

    def copy_template(filename):
        os.chdir(PAUTAS)
        template = "template.md"
        with open(template) as tpl:
            buf = tpl.read()
            with open(filename, 'w') as dest:
                dest.write(buf)

    def create_pauta():
        last_pauta = get_last_pauta()
        new_pauta = "%s.md" % generate_serial(last_pauta)
        copy_template(new_pauta)
        pauta_commit_push(new_pauta, "Adicionando nova pauta.")

    def is_allowed(username):
        if username is None or allowed_users is None:
            return False
        if username in allowed_users.split():
            return True
        return False

    def add_sugestao(msg, user):
        debug("add_sugestao()")
        msg = re.sub("^/addsugestao ", "", msg)
        last_pauta = get_last_pauta()
        pauta_body = read_pauta(last_pauta)

        content = pauta_body.split("\n\n")

        position = None
        for i in range(0, len(content)):
            if re.search("Sugestões via telegram", content[i]):
                position = i
                break
        content[position] += "\n%s | author=%s" % (msg, user)
        body = "\n\n".join(content)

        with open(last_pauta, 'w') as fd:
            fd.write(body)
        pauta_commit_push(last_pauta)
        return "sugestão adicionada"

    def get_info_from_url(url):
        debug("get_info_from_url()")
        debug(" * url=%s" % url)

        if not re.search("^http", url):
            debug(" * no http")
            return None

        req = requests.get(url)
        html = None

        debug(" * status_code=%d" % req.status_code)
        if req.status_code == 200:
            html = req.text
        else:
            return "Error lendo %s" % url

        if html is not None:
            soup = bs4.BeautifulSoup(html, "html")
            title = sanitize(soup.title.text)
            md_text = "* [%s](%s)" % (title, url)
            return md_text
        else:
            return "Error lendo %s" % url


    def add_news(section, msg, user):
        debug("add_news()")
        debug(" * section: %s" % section)
        debug(" * msg: %s" % msg)
        debug(" * user: %s" % user)
        MAP = {
            "addsugestao" : [
                "^Sugestões\n--",
                "sugestão adicionada" ],
            "addnoticias" : [
                "^Notícias\n---",
                "notícia adicionada" ],
            "addliberageral" : [
                "^Libera Geral (show me the code)\n--",
                "adicionado ao libera geral" ],
            "addobituario" : [
                "^Obituário\n--",
                "adicionado ao obituário. R.I.P." ]
                }
        MAP["add"] = MAP["addnoticias"]

        last_pauta = get_last_pauta()
        pauta_body = read_pauta(last_pauta)

        content = pauta_body.split("\n\n")

        if section == "addsugestao":
            msg += " | author=%s" % user
        else:
            msg = get_info_from_url(msg)
        position = None
        for i in range(0, len(content)):
            debug("content[%d]: %s" % (i, content[i]))
            if re.search(MAP[section][0], content[i]):
                position = i
                break
        if position is None:
            debug(" * no section found for %s" % section)
            debug(" * pattern=%s" % MAP[section][0])
            return "erro ao adicionar %s" % msg

        content[position] += "\n" + msg
        body = "\n\n".join(content)

        with open(last_pauta, 'w') as fd:
            fd.write(body)
        pauta_commit_push(last_pauta)
        return MAP[section][1]


    try:
        user = cmd.from_user.username
        text = cmd.text

        if re.search("^/pauta", text):
            debug("Lendo pautas")
            msg = read_pauta()

        elif re.search("^/addsugestao", text):
            section = "addsugestao"
            text = re.sub(".*" + section + " ", "", text)
            msg = add_news(section, text, user)

        elif re.search("^/add", text):
            if not is_allowed(cmd.from_user.username):
                msg = "Sem permissão pra enviar novas entradas."
            else:
                section, url = text.split()
                section = section[1:]
                msg = add_news(section, url, user)

        elif re.search("^/novapauta", cmd.text):
            if is_allowed(cmd.from_user.username):
                create_pauta()
                msg = read_pauta()
            else:
                msg = "Sem permissão pra enviar novas entradas."
        else:
            error("No commands found for: %s" % msg)

        bot.reply_to(cmd, msg)
    except Exception as e:
        try:
            bot.reply_to(cmd, "Erro: %s" % e)
        except Exception as z:
            print(u"%s" % z)

    os.chdir(curdir)
    if not msg:
        return

    msg_queue = []
    MAXSIZE = 4000 # hardcoded value
    msg_size = len(msg)
    if msg_size > MAXSIZE:
        # it must send in two parts to avoid errors
        msg_lines = msg.split("\n")
        msg_buff = ""
        for line in msg_lines:
            if len(msg_buff + line + "\n") > MAXSIZE:
                msg_queue.append(msg_buff)
                msg_buff = ""
            else:
                msg_buff += line + "\n"
        if len(msg_buff) > 0:
            msg_queue.append(msg_buff)
    else:
        msg_queue.append(msg)

    for msg in msg_queue:
        try:
            bot.send_message(cmd.chat.id, msg)
        except Exception as e:
            bot.reply_to(cmd, "Deu merda: %s" % e)


if __name__ == '__main__':
    if sys.argv[-1] == "check":
        print("Ok")
        sys.exit(os.EX_OK)
    try:
        debug("Main()")
        main()
        debug("Polling...")
        bot.polling()
    except Exception as e:
        print(e)
        debug(e)
    os.unlink(PIDFILE)
