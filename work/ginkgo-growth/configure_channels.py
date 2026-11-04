"""Operator-only channel setup. Credentials never printed or sent to AI."""
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
import tkinter as tk
from tkinter import ttk, messagebox

TARGET=Path(r'C:\Services\KaiqiuMatch_20260915')

def main():
    config=json.loads((TARGET/'runtime.json').read_text('utf-8-sig'))
    os.environ.update({str(k):str(v) for k,v in config.items() if v is not None})
    sys.path.insert(0,str(TARGET))
    from growth_channels import Channels, APPS, ORIGIN
    from growth_acquisition import Store
    from growth_permissions import protect_credentials
    root=TARGET/'growth-data'
    protect_credentials(root/'secrets')
    channels=Channels(SimpleNamespace(store=Store(root)))
    window=tk.Tk();window.title('银杏 · 官方客服安全配置 1.0.0');window.geometry('900x700')
    book=ttk.Notebook(window);book.pack(fill='both',expand=True,padx=20,pady=20)
    def entry(parent,label,value='',secret=False):
        ttk.Label(parent,text=label).pack(anchor='w',pady=(10,3))
        variable=tk.StringVar(value=value)
        widget=ttk.Entry(parent,textvariable=variable,width=110,show='*' if secret else '')
        widget.pack(fill='x');return variable,widget
    wx=ttk.Frame(book,padding=18);book.add(wx,text='微信小程序客服')
    ttk.Label(wx,text='微信后台选择：安全模式 / JSON。新密钥由你复制到官方后台；不要发到聊天。',wraplength=780).pack(anchor='w')
    _,_=entry(wx,'AppID',APPS['wechat'])
    callback,_=entry(wx,'接收地址',ORIGIN+'/callbacks/wechat')
    token,token_box=entry(wx,'Token（生成后复制到微信后台）')
    aes,aes_box=entry(wx,'EncodingAESKey（生成后复制到微信后台）')
    def show_wx():
        cfg=channels.config('wechat');token.set(cfg.get('token',''));aes.set(cfg.get('aes_key',''))
    show_wx()
    def save_wx():
        try:
            cfg=channels.config('wechat')
            if not cfg.get('token'):
                channels.update('wechat',{'generate_wechat_keys':True,'receive':True})
            else:
                channels.update('wechat',{'receive':True})
            show_wx()
            messagebox.showinfo('配置已保存','回调接收已准备，AI回复仍关闭。请复制地址、Token、EncodingAESKey到微信后台，安全模式选择JSON，再提交验证。')
        except Exception as e:messagebox.showerror('未保存',str(e)[:200])
    ttk.Button(wx,text='生成／保留微信配置（不发送消息）',command=save_wx).pack(anchor='w',pady=15)
    def test_wx():
        try:channels.access_token('wechat',channels.config('wechat'));messagebox.showinfo('验证成功','现有微信接口凭据可用；没有发送消息。')
        except Exception as e:messagebox.showerror('验证未通过',str(e)[:200])
    ttk.Button(wx,text='验证现有微信接口凭据（不重置）',command=test_wx).pack(anchor='w')
    dy=ttk.Frame(book,padding=18);book.add(dy,text='抖音经营私信')
    ttk.Label(dy,text='需要：开发配置 → Webhook 的专用AppSecret；以及已授权经营账号的OpenID。不是小程序登录密钥。',wraplength=780).pack(anchor='w')
    entry(dy,'AppID',APPS['douyin']);entry(dy,'接收地址',ORIGIN+'/callbacks/douyin')
    secret,secret_box=entry(dy,'Webhook AppSecret（仅在此窗口输入，留空保留现有配置）',secret=True)
    show_secret=tk.BooleanVar(value=False)
    ttk.Checkbutton(dy,text='显示密钥（便于粘贴核对；不要截图或发送）',variable=show_secret,
                    command=lambda:secret_box.configure(show='' if show_secret.get() else '*')).pack(anchor='w')
    owner,owner_box=entry(dy,'已授权经营账号 OpenID',channels.config('douyin').get('business_openid',''))
    def save_dy():
        try:
            channels.update('douyin',{'webhook_secret':secret.get(),'business_openid':owner.get(),'receive':True})
            secret.set('')
            messagebox.showinfo('配置已保存','私信回调接收已准备，AI回复仍关闭。请在抖音后台填写接收地址，订阅接收私信事件和发送私信事件。')
        except Exception as e:messagebox.showerror('未保存',str(e)[:200])
    ttk.Button(dy,text='保存抖音配置（不发送消息）',command=save_dy).pack(anchor='w',pady=15)
    def test_dy():
        try:channels.access_token('douyin',channels.config('douyin'));messagebox.showinfo('验证成功','经营账号的私信令牌获取成功；没有发送消息。')
        except Exception as e:messagebox.showerror('验证未通过',str(e)[:200])
    ttk.Button(dy,text='验证经营账号私信权限',command=test_dy).pack(anchor='w')
    note=ttk.Label(window,text='完成平台回调验证后，在获客工作台 → 渠道接入 → 接待开关中启用AI。关闭窗口不会重启服务。\n小红书解密规范仍待核实；快手暂无已验证的第三方消息API，本工具不会假称已连接。',wraplength=850)
    note.pack(anchor='w',padx=24,pady=15)
    window.mainloop()

if __name__=='__main__':
    try:main()
    except Exception as e:
        print('CONFIGURATION NOT COMPLETED: '+type(e).__name__+'. No credential is displayed.')
        raise SystemExit(1)
