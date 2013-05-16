# -*- coding: gbk -*-

from smlist import SMList, SMListFactory, cook_array, cook_string,\
    cook_gb_unicode
from jinja2 import Environment, FileSystemLoader
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
import itertools
import traceback
import json
import pickle
import time
import sys
from jinja2 import *

reload(sys)
sys.setdefaultencoding('utf-8')

MAIL_HOST = '----'
MAIL_USERS = []
MAIL_PASSWD = '------'
MAIL_PORT = '----'

file_factory = SMListFactory(
    '<16s14s14s56sIIIi12s',
    [('filename', cook_string),
     ('owner', cook_string),
     ('realowner', cook_string),
     ('title', cook_gb_unicode),
     'flag', 'size', 'id', 'filetime', 'reserved'])

user_info_factory = SMListFactory(
    '<iiiiiiiiiiii10s60scii14s21s21sc' + 'H' * 232 + 'iiHi',
    ['active',
     'uid',
     'pid',
     'invisible',
     'sockactive',
     'sockaddr',
     'destuid',
     'mode',
     'pager',
     'in_chat',
     'fnum',
     ('chatid',cook_string),
     ('from',cook_string),
     'hideip',
     'idle_time',
     'deactive_time',
     ('userid',cook_string),
     ('realname',cook_string),
     ('username',cook_string),
     'nickcolor',
     ('friends',cook_array),
     ('reject',cook_array),
     'utmpkey']
)

board_factory = SMListFactory(
    '<20s40s40sIIIIII4s',
    [('boardname', cook_string),
     ('title', cook_gb_unicode),
     ('bm', cook_array),
     'flag',
     'level',
     'lastpost',
     'total',
     'parent',
     'total_today',
     'reserved'])

userrec_factory = SMListFactory(
    '<16sI16sII2s16s21s21s16s64sI1s7sIII21s80s71sII1s1s1s1siIIi',
    [('userid', cook_gb_unicode),
     'firstlogin',
     ('lasthost', cook_string),
     'numlogins',
     'numposts',
     ('flags', cook_string),
     ('passwd', cook_string),
     ('username', cook_string),
     ('ident', cook_string),
     ('termtype', cook_string),
     ('reginfo', cook_string),
     'userlevel',
     'usertitle',
     ('reserved', cook_string),
     'lastlogin',
     'lastlogout',
     'stay',
     ('realname', cook_string),
     ('address', cook_string),
     ('email', cook_string),
     'nummails',
     'lastjustify',
     'gender',
     'birthyear',
     'birthmonth',
     'birthday',
     'signature',
     'userdefine',
     'notedate',
     'noteline'])

def b():
    return board_factory.connect('/home/bbs/bbs_home/.BOARDS')

def u(filename):
    return userrec_factory.connect('/home/bbs/bbs_home/' + filename)

def f(filename):
    return file_factory.connect('/home/bbs/bbs_home/' + filename)

class MainUserData :

    db_filename = 'db/mailchecker'

    def __init__(self,version = 0 ):
        self.version = version
        try:
            self._db = pickle.load(open(self.db_filename))
        except:
            self._db = {}

    def set_user(self,user):
        self._user = user
        userid = self._user['userid']
        if userid not in self._db :
            self._db[userid] = {}
        return self.check_special_setting()

    def set_bbs_path(self,path):
        self._path = path

    def check_special_setting(self):
        self.path = self._path + '/home/%s/%s/setting' % (self._user['userid'][0].upper(),self._user['userid'])
        try :
            self._setting = pickle.load(open(path))
        except :
            self._setting = {'no_hint_mail':'0'}
        if self._setting['no_hint_mail'] == '1':
            return True
        return False
        
    def check_version(self):
        if self._db[self._user['userid']].get('mark') == self.version :
            return True
        return False

    def get_last_login(self):
        return self._user["lastlogout"]

    def set_version(self):
        self._db[self._user['userid']]['mark'] = self.version
        self.finish()

    def finish(self):
        pickle.dump(self._db, open(self.db_filename, 'w'),
                    pickle.HIGHEST_PROTOCOL)
        pickle.dump(self._setting, open(self.path, 'w'),
                    pickle.HIGHEST_PROTOCOL)


class Checkers(object):

    def set_user(self,user):        
        self.userid = user["userid"]
        self.last_logout = user["lastlogout"]

    def set_bbs_path(self,path):
        self._path = path
    
    def check_to_send_mail(self):
        path = 'mail/%s/%s/.DIR' % (self.userid[0].upper(),self.userid)
        try :
            lastmail = f(path)
        except IOError :
            return False
        if lastmail[-1]['flag'] & 1:
            return False
        return True

    def find_out_update_boards(self):
        path = self._path + '/home/%s/%s/.goodbrd' % (self.userid[0].upper(),self.userid)
        try :
            gdbs = open(path,'r+')
        except IOError :
            return []
        result = []
        goodbrd = gdbs.readlines()
        if int(time.time()) - self.last_logout < 2.5 * 24 * 60 * 60 :
            return []
        for board in goodbrd :
            try:
                d = f('boards/%s/.DIR'%board[:-1])
                lastpost = d[-1]["filetime"]
            except :
                continue
            if lastpost > self.last_logout :
                result.append(board)
        return result

class MailDataCollecter:
    
    db_filename = 'db/mailchecker'

    def __init__(self):
        self.sender = MailSender(MAIL_USERS, MAIL_PASSWD, MAIL_HOST, MAIL_PORT)
        self.user_data =  MainUserData(int(time.time()) - int(time.time()) % ( 24 * 60 * 60 ))
        self.checkers = Checkers()
        self.template = 'mail.html'
    
    def set_bbs_path(self,path):
        self.checkers.set_bbs_path(path)
        self.user_data.set_bbs_path(path)

    def get_email_contain(self,update_board,new_mail,userid):
        env = Environment(loader = FileSystemLoader('templates'))
        tpl = env.get_template(self.template)
        new_board_len = len(update_board)
        return tpl.render(userid=userid,
                          update_board=update_board,
                          new_board_len=new_board_len,
                          new_mail=new_mail)

    def collect(self):
        for user in u('.PASSWDS'):
            if self.user_data.set_user(user) or self.user_data.check_version():
                continue
            if not user.get('email') :
                continue
            self.checkers.set_user(user)
            update_board = self.checkers.find_out_update_boards()
            new_mail = self.checkers.check_to_send_mail()
            if new_mail is False and len(update_board) == 0 :
                continue
            email_contain = self.get_email_contain(update_board,new_mail,user["userid"])
            temp_mark = False
            while not temp_mark :
                temp_mark = self.sender.sendmail(user['email'],email_contain)
            self.user_data.set_version()
            self.user_data.finish()
            
        
    
        
class MailSender:

    def __init__(self, userids, passwd, host, port=994):
        self._uiter = itertools.cycle(userids)
        self._passwd = passwd
        self._host = host
        self._port = port
        self.use_next()

    def reconnect(self):
        self._sender = smtplib.SMTP_SSL(self._host, self._port)
        self._sender.login(self._userid, self._passwd)

    def use_next(self):
        time.sleep(5)
        self._userid = self._uiter.next()
        print '%% Use %s' % self._userid
        self._me = (u'"逸仙时空"<%s@163.com>' % self._userid)#.encode('UTF-8')
        self.reconnect()

    def get_whole_mail(self,to, subject, html):
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['To'] = to
        msg['Content-Type'] = "text/html; charset=UTF-8"
        part = MIMEText(html.encode('UTF-8'), 'html', _charset='utf-8')
        msg.attach(part)
        return msg

    def sendmail(self,t,html):
        s = self.get_whole_mail(t,'argo邮件提醒',html)
        s['From'] = self._me
        try:
            self._sender.sendmail(self._me, t, s.as_string())
            return True
        except (smtplib.SMTPServerDisconnected, smtplib.SMTPRecipientsRefused) as e:
            traceback.print_exc()
            if e[0] == 550:
                return True
            self.reconnect()
            return False
        except (smtplib.SMTPSenderRefused, smtplib.SMTPDataError) as e:
            traceback.print_exc()
            if e[1].startswith('MI:DMC') :
                self.reconnect()
                return False
            if e[1].startswith('MI:SFQ') :            
                time.sleep(600)
                return False
            if e[1].startswith('RP:QRC') :
                self.use_next()
                return False
            if e[1].startswith('DT:SPM') :
                time.sleep(120)
                self.use_next()
                return False
            if e[0] == 550:
                return True
            raise e


