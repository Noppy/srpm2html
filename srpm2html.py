#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  srpm2html
#  ======
#  Copyright (C) 2017 n.fujita
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
from __future__ import print_function

import sys
import os
import argparse
import pprint
import urllib
import urllib2
import glob
import shutil
import subprocess
import re

#------------------------
# global configuration
#------------------------
class config:
    def __init__(self,args):
        self.env_lang        = 'C'
        self.env_path        = '/usr/local/bin:/bin:/usr/bin:/usr/local/sbin:/usr/sbin:/sbin:~/.local/bin:~/bin'
        self.fstab_tmp       = ''
        self.args            = args
        self.srpm_file       = ''
        self.url_download_ok = False
        self.srpm_name       = ''
        self.srpm_version    = ''
        self.spec            = ''
        self.is_kernel_srpm  = False
        self.build_src_top   = ''
        self.squashfs_html   = ''
        self.squashfs_src    = ''

#------------------------
# functions
#------------------------
def get_args():
    parser = argparse.ArgumentParser( \
        description='Generate a HTML from a SRPM source package.')
    parser.add_argument('-d', '--debug',  \
            action='store_true',          \
            default=False,                \
            help='show some debugging output')

    parser.add_argument('-N', '--notpostprocess', \
            action='store_true',          \
            default=False,                \
            help='Do not postporcess')

    parser.add_argument('-t', '--tmpdir', \
            action='store',               \
            default='/tmp',               \
            type=str,                     \
            help='specify a working directory')

    parser.add_argument('-r', '--rpmbuilddir',           \
            action='store',                              \
            default=os.path.expanduser('/data/rpmbuild'),\
            type=str,                                    \
            help='specify rpmbuild topdir')

    parser.add_argument('-s', '--squashfsdir', \
            action='store',                    \
            default='/data/squashfs',          \
            type=str,                          \
            help='specify squashfs directory')

    parser.add_argument('-K', '--http_kernelsdir',  \
            action='store',                 \
            default='/data/kernel',         \
            type=str,                       \
            help='specify directory which is the parent of kernel\'s html mount point')

    parser.add_argument('-T', '--http_toolsdir',  \
            action='store',                       \
            default='/data/tools',                \
            type=str,                             \
            help='specify directory which is the parent of other\'s html mount point')

    parser.add_argument('-S', '--sourcedir',  \
            action='store',                   \
            default='/data/source',           \
            type=str,                         \
            help='specify source code directory' )

    parser.add_argument('url',              \
            metavar='SRPM_FilePath_or_URL', \
            action='store',                 \
            type=str,                       \
            help='specify a Source Package(SRPM)\'file path or URL.')
    return( parser.parse_args() )


def show_args(args):
    pp = pprint.PrettyPrinter(indent=1, stream=sys.stdout)
    sys.stdout.write('-----------------------------------'+'\n')
    sys.stdout.write('arguments list'+'\n')
    pp.pprint(vars(args))
    sys.stdout.write('-----------------------------------'+'\n')


def debug_print(flag, msg):
    if flag:
        if isinstance(msg,list):
            m = ','.join(msg)
        else:
            m = msg
        #sys.stderr.write(m+'\n')
        sys.stdout.write(m+'\n')


def err_print(msg):
    debug_print(True, msg)


def info_print(msg):
    if isinstance(msg, list):
        m = '.'.join(msg)
    else:
        m = msg
    sys.stdout.write(m+'\n')


def exec_subprocess(cmd):
    try:
        r = subprocess.check_output(
            cmd,
            stderr = subprocess.STDOUT
            )
        sys.stdout.write(r+'\n')

    except OSError as e:
        debug_print(
            True, #conf.args.debug,
            'file ='     +str(e.filename)+'\n' \
                +'errno='+str(e.errno)   +'\n' \
            )
        err_print( str(e.strerror) )
        return(False)

    except subprocess.CalledProcessError as e:
        debug_print(
            True, #conf.args.debug,
            'ret='     +str(e.returncode)+'\n' \
                +'cmd='+str(e.cmd)
            )
        info_print(str(e.output))
        return(False)
    return(True)


def remove_dirs_files(conf, files):
    for f in files:

        if os.path.isdir(f):
            debug_print(conf.args.debug, 'remove dir :"'+f+'"')
            try:
                shutil.rmtree(f)
            except:
                pass
        elif os.path.isfile(f):
            debug_print(conf.args.debug, 'remove file:"'+f+'"')
            try:
                os.remove(f)
            except:
                pass


def init_process(conf):
    info_print('<<<Initialize>>>')
    
    #set enviroment 
    os.environ["LANG"] = conf.env_lang
    os.environ["PATH"] = conf.env_path

    #set the temporary file for adding data to fstab.
    conf.fstab_tmp = conf.args.tmpdir + '/fstab_tmp.' + str(os.getpid())

    #remove existed files
    files = glob.glob(conf.args.rpmbuilddir + '/*')
    remove_dirs_files(conf,files)


def end_process(conf, success=False):
    info_print('<<<End processing>>>')    
   
    #If "not-postprocess" is true, exit without postprocess.
    if conf.args.notpostprocess:
        sys.exit()
    
    #remove files
    files = []
    if conf.url_download_ok:
        files.append( conf.srpm_file )
    files.append( conf.fstab_tmp )
    files.extend(glob.glob(conf.args.rpmbuilddir + '/*'))
    if not success:
        files.append( conf.squashfs_html )
        files.append( conf.squashfs_src )
    
    remove_dirs_files(conf,files)
    
    #exit
    sys.exit()


def check_line_in_file(target_file,pattern):
    ret = False

    # set pattern
    r = re.compile(pattern)

    #open file
    try:
        fd = open(target_file,'r')
    except:
        err_print('Can not open "'+target_file)
        return(ret)

    #check line
    for line in fd:
        if r.match(line):
            ret = True
            break

    #return
    return(ret)


def get_srpm(conf):
    info_print('<<<Get a srpm file.>>>')

    tmpdir = conf.args.tmpdir
    url    = conf.args.url
    ret = ''

    f = os.path.abspath( tmpdir \
            + '/' + (os.path.basename(url) or 'index.html') )
    try:
        #URLが存在しているかチェック
        urllib2.urlopen(url)
    except:
        #存在していない場合ローカルファイルのパスかチェック
        if os.path.isfile(url):
            ret = url
    else:
        #URLが存在する場合ファイルをダウンロード
        urllib.urlretrieve(url, f)
        conf.url_download_ok = True
        ret = f

    # check and store
    if ret == '':
        #Can not download url file
        err_print('Can not get a srpm file(Abort).')    
        end_process(conf)
    else:
        debug_print(conf.args.debug, 'Download File:' + ret)
        conf.srpm_file = ret


def install_srpm(conf):
    info_print('<<<<Install srpm package>>>')
    ret = False

    #srpmファイル名前の取得
    cmd = [ 'rpm','-q','--qf=%{NAME}','-p', conf.srpm_file ]
    debug_print(conf.args.debug,cmd)
    try:
        conf.srpm_name = subprocess.check_output(cmd, \
                stderr=open("/dev/null","w"))
    except:
        err_print('Can not get srpm name:'+conf.srpm_file+'.')    
        end_process(conf)
    debug_print(conf.args.debug, 'srpm_name:'+conf.srpm_name)

    #srpmファイルバージョンの取得
    cmd = [ 'rpm','-q','--qf=%{VERSION}-%{RELEASE}','-p', conf.srpm_file ]
    debug_print(conf.args.debug,cmd)
    try:
        conf.srpm_version = subprocess.check_output(cmd, \
                stderr=open("/dev/null","w"))
    except:
        err_print('Can not get srpm version:'+conf.srpm_file+'.')    
        end_process(conf)
    debug_print(conf.args.debug, 'srpm_version:'+conf.srpm_version)

    #srpmファイルの展開
    cmd = [ 'rpm','-ivh', \
            '--define=%_topdir '+conf.args.rpmbuilddir, \
            conf.srpm_file ]
    debug_print(conf.args.debug,cmd)

    if not exec_subprocess(cmd):
        err_print('Can not install '+conf.srpm_file+'.')    
        end_process(conf)

    debug_print(conf.args.debug, 'done to install srpm')

    # specファイルのパス取得
    try:
        files = glob.glob(conf.args.rpmbuilddir + '/SPECS/*.spec')
    except:
        err_print('Not found a SPEC file(None)')
        end_process(conf)

    if os.path.isfile(files[0]):
        conf.spec = files[0]
    else:
        err_print('Not found a SPEC file('+files[0]+')')
        end_process(conf)
    debug_print(conf.args.debug, 'spec file:'+conf.spec)


def rpmbuild(conf):
    info_print('<<<<extrace source cord>>>')

    # srpmの種別(カーネルかそれ以外かのチェック)
    debug_print(conf.args.debug,'check srpm type. srpm_name:'+conf.srpm_name)
    re_kernel = re.compile("^kernel$")
    if re_kernel.match(conf.srpm_name) is not None:
        conf.is_kernel_srpm = True
        debug_print(conf.args.debug,conf.srpm_name+' is kernel srpm.')
    else:
        conf.is_kernel_srpm = False
        debug_print(conf.args.debug,conf.srpm_name+' is other srpm.')

    #rpmbuildによるソースコードの展開
    cmd = [ 'rpmbuild', \
            '--define=%_topdir '+conf.args.rpmbuilddir, \
            '--nodeps','-bp',conf.spec ]
    debug_print(conf.args.debug,cmd)
    if not exec_subprocess(cmd):
        err_print('abend "rpmbuild -bp" command.')    
        end_process(conf)
    debug_print(conf.args.debug, 'done to buildsrpm')

    #ソースコードのディレクトリ取得
    if conf.is_kernel_srpm:
        p = conf.args.rpmbuilddir + '/BUILD/*/linux*/'
    else:
        p = conf.args.rpmbuilddir + '/BUILD/*/'
    try:
        files = glob.glob(p)
    except:
        err_print('Not found a BUILD directory(None)')
        end_process(conf)

    if os.path.isdir(files[0]):
        conf.build_src_top = files[0]
    else:
        err_print('Not found a BUILD directory('+files[0]+')')
        end_process(conf)
    debug_print(conf.args.debug, 'BUILD top directory:'+conf.build_src_top)

def htags(conf):
    info_print('<<<<generate html files from source code>>>')

    #カレントディレクトリの移動
    #(BUILDしたソースコードのトップディレクトリに移動)
    try:
        os.chdir(conf.build_src_top)
    except:
        err_print('Can not change directory('+conf.build_src_top+')')
        end_process(conf)

    #set main function
    if conf.is_kernel_srpm:
        main_func = 'start_kernel'
    else:
        main_func = 'main'

    #htags
    cmd = [ 'htags', '--gtags', '--frame', '--alphabet', '--line-number', \
            '--symbol', '-other', '--main-func', main_func, \
            '--title', conf.srpm_name+'-'+conf.srpm_version ]
    debug_print(conf.args.debug, cmd)

    if not exec_subprocess(cmd):
        err_print('abend htags command.')    
        end_process(conf)
    debug_print(conf.args.debug, 'done to htags')


def mksquash(conf):
    info_print('<<<<make the squash file>>>')

    #set squashfs file name
    conf.squashfs_thml = conf.args.squashfsdir+'/' \
            +conf.srpm_name+'-'+conf.srpm_version+'_html.squashfs'
    conf.squashfs_src  = conf.args.squashfsdir+'/' \
            +conf.srpm_name+'-'+conf.srpm_version+'_source.squashfs'

    #create the squash file of html files 
    cmd = [ 'mksquashfs', './HTML', conf.squashfs_thml, '-noappend', '-no-progress' ]
    debug_print(conf.args.debug, cmd)

    if not exec_subprocess(cmd):
        err_print('abend mksquashfs command(html).')    
        end_process(conf)
    debug_print(conf.args.debug, 'done to mksquashfs(html)')

    #remove global data
    f = [ conf.build_src_top+'HTML',   \
          conf.build_src_top+'GPATH', conf.build_src_top+'GRTAGS', conf.build_src_top+'GTAGS' ]
    remove_dirs_files( conf, f )

    #create the squash file of source code files 
    cmd = [ 'mksquashfs', './', conf.squashfs_src, '-noappend', '-no-progress' ]
    debug_print(conf.args.debug, cmd)

    if not exec_subprocess(cmd):
        err_print('abend mksquashfs command(source code).')    
        end_process(conf)
    debug_print(conf.args.debug, 'done to mksquashfs(source)')
    

def mountfs(conf):
    info_print('<<<<make mount point,add entories at fstab, and mount>>>')

    #set mountpoint path
    if conf.is_kernel_srpm:
        mpt_html = conf.args.http_kernelsdir+'/' \
                   +conf.srpm_name+'-'+conf.srpm_version
    else:
        mpt_html = conf.args.http_toolsdir+'/' \
                   +conf.srpm_name+'-'+conf.srpm_version
   
    mpt_src = conf.args.sourcedir+'/' \
              +conf.srpm_name+'-'+conf.srpm_version


    #マウントポイントディレクトリ作成
    for f in [ mpt_html, mpt_src ]:
        try:
            os.mkdir(f)
        except OSError as e:
            err_print(e.strerror+ \
                ' (errno='+str(e.errno)+' file='+e.filename+')') 

    #fstabへの登録
    for (mpt, fs) in [
                        [ mpt_html, conf.squashfs_thml ],
                        [mpt_src,  conf.squashfs_src   ]
                      ]: 
        line = fs + ' ' + mpt + ' squashfs loop 2 2'
        if check_line_in_file('/etc/fstab',line):
            info_print('the duplicating line. :'+line)
        else:
            # add the new mount point entry.
            cmd = [ 'sudo', 'sed', '-i','-e', '$ a\\'+line, '/etc/fstab' ]
            debug_print(conf.args.debug, cmd)
            try:
                subprocess.check_output(cmd)
            except:
                err_print('can not add new line at fstab.')    
                end_process(conf)
            debug_print(conf.args.debug, 'done to add new line at fstab')
            
    #mount実行
    cmd = [ 'sudo', 'mount', '-a' ]
    debug_print(conf.args.debug, cmd)

    if not exec_subprocess(cmd):
        err_print('can not moun.')    
        end_process(conf)
    debug_print(conf.args.debug, 'done to mount')


#------------------------
# Main
#------------------------
if __name__ == "__main__":
   
    # 引数の処理 
    conf = config(get_args())
    if conf.args.debug:
        show_args(conf.args)

    #初期化
    init_process(conf)

    #メイン処理
    get_srpm(conf)     # SRPMファイルの取得
    install_srpm(conf) #srpmファイルの展開
    rpmbuild(conf)     #rpmbuildによるソースファイル展開
    htags(conf)        #Gnu globalによる解析&html変換
    mksquash(conf)     #生成したhtagsデータをsquashファイル形式に変換
    mountfs(conf)      #squashfsのマウント

    #終了処理
    end_process(conf,success=True)