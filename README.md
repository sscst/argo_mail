argo_mail
=========

中山大学逸仙时空邮件提醒小脚本

from bbs import MailDataCollecter()

c = MailDataCollecter()

c.set_bbs_path('../bbs_home')   #一定要在此处设定bbs_home的地址

c.collect()                     #即可运行
