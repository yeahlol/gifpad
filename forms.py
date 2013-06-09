#!/usr/bin/python
# -*- coding: utf-8 -*-

import re
from flaskext.babel import gettext, lazy_gettext
from wtforms import Form, TextField, TextAreaField, PasswordField, SelectField, HiddenField, validators
from wtforms.validators import Required, Length, Regexp, Optional, EqualTo, URL


class Sign_upform(Form):
    username = TextField(lazy_gettext(u'Username'), validators=[Required(lazy_gettext(u'Enter Username')),
                         Length(min=2,max=25, message=lazy_gettext(u"Field must be between 2 and 25 characters long")),
                         Regexp("^[a-zA-Z0-9_]+$", message=lazy_gettext(u"Letters and numbers and underscore only"))])

    password = PasswordField(lazy_gettext(u'Password'), validators=[Required(lazy_gettext(u'Enter Password')),
                             Length(min=8,max=30, message=lazy_gettext(u"Field must be between 8 and 30 characters long")),
                             Regexp("^[a-zA-Z0-9]+$", message=lazy_gettext(u"Letters and numbers only"))])

    email = TextField(u'Email(optional)', validators=[Optional(),
                      Length(min=2,max=50, message=lazy_gettext(u"Field must be between 2 and 50 characters long")),
                      Regexp("^\w[\w\.\-\_]*[^\.]@\w[\w\-]*(\.[\w\-]{1,})+[^\.]$", message=lazy_gettext(u"Invalid Email"))])

    def validate_banned_username(self):
      banned_usernames = ['user', 'gif', 'submit', 'board', 'upload', 'tag', 'page', 'gif_delete', 'comment', 'password',
                          'resetpassword', 'authorize', 'oauth']
      for banned_username in banned_usernames:
        if self.username.data == banned_username:
          return u"username"
      return False 


class Sign_inform(Form):
    username = TextField(lazy_gettext(u'Username'), validators=[Required(lazy_gettext(u'Enter Username')),
                         Length(min=2,max=25, message=lazy_gettext(u"Field must be between 2 and 25 characters long")),
                         Regexp("^[a-zA-Z0-9_]+$", message=lazy_gettext(u"Letters and numbers and underscore only"))])

    password = PasswordField(lazy_gettext(u'Password'), validators=[Required(lazy_gettext(u'Enter Password')),
                         Length(min=8,max=30, message=lazy_gettext(u"Field must be between 8 and 30 characters long")),
                         Regexp("^[a-zA-Z0-9]+$", message=lazy_gettext(u"Letters and numbers only"))])


class Passwordform(Form):
    username = TextField(lazy_gettext(u'Username:'), validators=[Required(lazy_gettext(u'Enter Username')),
                         Length(min=2,max=25, message=lazy_gettext(u"Field must be between 2 and 25 characters long")),
                         Regexp("^[a-zA-Z0-9_]+$", message=lazy_gettext(u"Letters and numbers and underscore only"))])

    
class ResetPwform(Form):
    newpassword = PasswordField(lazy_gettext(u'New Password'), validators=[Required(lazy_gettext(u'Enter New Password')),
                         Length(min=8,max=30, message=lazy_gettext(u"Field must be between 8 and 30 characters long")),
                         Regexp("^[a-zA-Z0-9]+$", message=lazy_gettext(u"Letters and numbers only")),
                         EqualTo('verifypassword', message=lazy_gettext(u"Passwords must match"))])

    verifypassword = PasswordField(lazy_gettext(u'Verify Password'), validators=[Required(lazy_gettext(u'Enter New Password')),
                         Length(min=8,max=30, message=lazy_gettext(u"Field must be between 8 and 30 characters long")),
                         Regexp("^[a-zA-Z0-9]+$", message=lazy_gettext(u"Letters and numbers only"))])


class AddGifform(Form):
    source_url = TextField(u'URL', validators=[Required(lazy_gettext(u'Enter URL')), URL(message=lazy_gettext(u'Invalid URL'))])


class CreateGifform(Form):
    board = SelectField(lazy_gettext(u"Choose a Board:"), validators=[Required(lazy_gettext(u"Enter boardname"))], coerce=int)

    description = TextAreaField(lazy_gettext(u"Description(optional):"), validators=[Optional(),
                                Length(min=0,max=200,message=lazy_gettext(u"Field must be between 0 and 200 characters long"))])

    def validate_tags(self, tags):
      if len(tags) > 5 or len(tags) == 0:
        self.errors["tag_items"] = lazy_gettext(u"Please don't use more than 6 tags") if len(tags) > 5 else lazy_gettext(u"Enter tag")
        return False
      else:
        for tag in tags:  # 単一のタグが21文字以上で構成されている場合はerror分岐
          if len(tag) == 0 or len(tag) >= 21:
            self.errors["tag_length"] = lazy_gettext(u"Tag must be between 1 and 20 characters long")
            return False
        for tag in tags:  # 単一のタグがひらカナ漢字, 半角英字, 半角全角数字アンダースコアハイフン以外で構成されている場合はerror分岐
          if not re.compile(u"^([a-zA-Z0-9_-]|[０-９ぁ-ん＿ー]|[ァ-ヴ]|[一-龠])+$").search(tag):
            self.errors["tag_re"] = lazy_gettext(u"Letters and numbers only")
            return False
      return True 


class UploadGifform(Form):
    board = SelectField(lazy_gettext(u"Choose a Board:"), validators=[Required(u"Enter boardname")], coerce=int)

    hidden = HiddenField(u'Hidden', validators=[Required(u"hogehoge")])


class CreateBoardform(Form):
    board = TextField(lazy_gettext(u"Boardname:"), validators=[Required(lazy_gettext(u"Enter boardname")),
                      Length(min=2,max=80,message=lazy_gettext(u"Field must be between 2 and 80 characters long")),
                      Regexp(u"^([a-zA-Z0-9_-]|[ぁ-ん０-９＿ー]|[ァ-ヴ]|[一-龠])+$", message=lazy_gettext(u"Letters and numbers only"))])

    description = TextAreaField(lazy_gettext(u"Description(optional):"), validators=[Optional(),
                                Length(min=0,max=200,message=lazy_gettext(u"Field must be between 0 and 200 characters long"))])


class EditBoardform(Form):
    board = TextField(lazy_gettext(u"Boardname:"), validators=[Required(lazy_gettext(u"Enter boardname")),
                      Length(min=2,max=80,message=lazy_gettext(u"Field must be between 2 and 80 characters long")),
                      Regexp(u"^([a-zA-Z0-9_-]|[ぁ-ん０-９＿ー]|[ァ-ヴ]|[一-龠])+$", message=lazy_gettext(u"Letters and numbers only"))])

    description = TextAreaField(lazy_gettext(u"Description(optional):"), validators=[Optional(),
                      Length(min=1,max=200,message=lazy_gettext(u"Field must be between 0 and 200 characters long"))])


class EditGifform(Form):
    board = SelectField(lazy_gettext(u"Choose a Board:"), validators=[Required(lazy_gettext(u"Enter boardname"))], coerce=int)

    description = TextAreaField(lazy_gettext(u"Description(optional):"), validators=[Optional(),
                      Length(min=1,max=200,message=lazy_gettext(u"Field must be between 0 and 200 characters long"))])

    def validate_tags(self, tags):
      if len(tags) > 5 or len(tags) == 0 :
        self.errors["tag_items"] = lazy_gettext(u"Please don't use more than 6 tags") if len(tags) > 5 else lazy_gettext(u"Enter tag")
        return False
      else:
        for tag in tags:  # 単一のタグが21文字以上で構成されている場合はerror分岐
          if len(tag) == 0 or len(tag) >= 21:
            self.errors["tag_length"] = lazy_gettext(u"Tag must be between 1 and 20 characters long")
            return False
        for tag in tags:  # 単一のタグがひらカナ漢字, 半角英字, 半角全角数字アンダースコアハイフン以外で構成されている場合はerror分岐
          if not re.compile(u"^([a-zA-Z0-9_-]|[ぁ-ん０-９＿ー]|[ァ-ヴ]|[一-龠])+$").search(tag):
            self.errors["tag_re"] = lazy_gettext(u"Letters and numbers only")
            return False
      return True 


class Regifform(Form):
    board = SelectField(lazy_gettext(u"Choose a Board:"), validators=[Required(lazy_gettext(u"Enter boardname"))], coerce=int)
    description = TextAreaField(lazy_gettext(u"Description(optional):"), validators=[Optional(),
                                Length(min=0,max=200,message=lazy_gettext(u"Field must be between 0 and 200 characters long"))])

    def validate_tags(self, tags):
      if len(tags) > 5 or len(tags) == 0:
        self.errors["tag_items"] = lazy_gettext(u"Please don't use more than 6 tags") if len(tags) > 5 else lazy_gettext(u"Enter tag")
        return False
      else:
        for tag in tags:  # 単一のタグが21文字以上で構成されている場合はerror分岐
          if len(tag) == 0 or len(tag) >= 21:
            self.errors["tag_length"] = lazy_gettext(u"Tag must be between 1 and 20 characters long")
            return False
        for tag in tags:  # 単一のタグがひらカナ漢字, 半角英字, 半角全角数字アンダースコアハイフン以外で構成されている場合はerror分岐
          if not re.compile(u"^([a-zA-Z0-9_-]|[０-９ぁ-ん＿ー]|[ァ-ヴ]|[一-龠])+$").search(tag):
            self.errors["tag_re"] = lazy_gettext(u"Letters and numbers only")
            return False
      return True 


class Settingform(Form):
    email = TextField(u'Email:', validators=[Optional(),
                      Length(min=2,max=50,message=lazy_gettext(u"Field must be between 2 and 50 characters long")),
                      Regexp("^\w[\w\.\-\_]*[^\.]@\w[\w\-]*(\.[\w\-]{1,})+[^\.]$")])
    aboutuser = TextAreaField(lazy_gettext(u"About you:"), validators=[Optional(),
                              Length(min=0,max=150,message=lazy_gettext(u"Field must be between 0 and 150 characters long"))])


class ChangePwform(Form):
    currentpw = PasswordField(lazy_gettext(u"Current Password:"), validators=[Required(lazy_gettext(u'Enter Current Password')),
                              Length(min=8,max=30,message=lazy_gettext(u"Field must be between 8 and 30 characters long")),
                              Regexp("^[a-zA-Z0-9]+$", message=lazy_gettext("Letters and numbers only"))])
    newpw = PasswordField(lazy_gettext(u"New Password:"), validators=[Required(lazy_gettext(u'Enter New Password')),
                          Length(min=8,max=30,message=lazy_gettext(u"Field must be between 8 and 30 characters long")),
                          Regexp("^[a-zA-Z0-9]+$", message=lazy_gettext(u"Letters and numbers only")),
                                                     EqualTo('confirm_newpw', message=lazy_gettext(u"Passwords must match"))])
    confirm_newpw = PasswordField(lazy_gettext(u"Confirm New Password:"), validators=[Required(lazy_gettext(u"Enter New Password")),
                                  Length(min=8,max=30,message=lazy_gettext(u"Field must be between 8 and 30 characters long")),
                                                    Regexp("^[a-zA-Z0-9]+$", message=lazy_gettext("Letters and numbers only"))])
