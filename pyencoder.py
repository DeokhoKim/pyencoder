#!/usr/bin/env python

import os, sys, re
import logging
import subprocess

def ffmpeg():
  path = os.path.dirname(os.path.realpath(__file__))
  bin = os.path.join(path, 'ffmpeg', 'bin', 'ffmpeg.exe')
  if not os.path.exists(bin):
    return None
  return bin

def command(cmd):
  logging.info(cmd)
  p = subprocess.Popen(cmd, stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  (out, err) = p.communicate()
  return out, err
  
def getFiles(dir):
  excluded = [
    re.sub(r"\.(cq\d+|hevc)\.mp4", ".mp4", f)
    for root, dirs, fs, in os.walk(dir)
      for f in fs
        if re.match(r".*\.(cq\d+|hevc).mp4", f)
  ]
  files = [
    os.path.join(root, f)
    for root, dirs, fs, in os.walk(dir)
      for f in fs
        if f.endswith('.mp4')
        # and not f in excluded
        and not re.match(r".*\.(cq\d+|hevc).mp4", f)
  ]
  return files

def subname(name, cq):
  return re.sub('.mp4', '.cq{}.mp4'.format(cq), name)

def retname(name):
  return re.sub('.mp4', '.hevc.mp4', name)
  
def encode_hevc_fast(name, cq):
  # out, err = command([
  #   ffmpeg(),
  #   '-loglevel', 'error',
  #   '-y', '-i', "{}".format(name),
  #   '-c:v', 'hevc_nvenc', '-preset', 'slow', '-cq', str(cq),
  #   '-c:a', 'copy', subname(name, cq)
  # ])
  out, err = command([
    ffmpeg(),
    '-loglevel', 'error',
    '-y', '-i', "{}".format(name),
    '-c:v', 'libx265', '-preset', 'ultrafast', '-crf', str(cq),
    '-c:a', 'copy', subname(name, cq)
  ])

def encode_hevc(name, cq):
  out, err = command([
    ffmpeg(),
    '-loglevel', 'error',
    '-y', '-i', "{}".format(name),
    '-c:v', 'libx265', '-preset', 'veryslow', '-crf', str(cq),
    '-c:a', 'copy', subname(name, cq)
  ])

def compare_ssim_psnr(name, cq):
  out, err = command([
    ffmpeg(),
    '-hide_banner', '-loglevel', 'info',
    '-i', "{}".format(subname(name, 1)), '-i', "{}".format(subname(name, cq)),
    '-lavfi', "ssim; [0:v][1:v]psnr", '-f', 'null', '-'
  ])
  err = err.split(b'\r\n')[-3:-1]
  err[0] = re.sub(r".*All:([0-9.]+).*", r"\1", err[0].decode('utf-8'))
  err[1] = re.sub(r".*average:([0-9.a-z]+) min.*", r"\1", err[1].decode('utf-8'))
  
  if err[1]=='inf':
    err[1] = '50'
  
  err = map(float, err)
  err = [ round(r, 2) for r in err]
  return err

def loss(name, cq):
  encode_hevc_fast(name, cq)
  return compare_ssim_psnr(name, cq)


def encode_search(name):
  LOSS = [(0, 0) for i in range(52)] # (SSIM, PSNR)
  encode_hevc_fast(name, 1)

  L=0
  R=51

  while L<=R:
    M=(L+R)//2
    LOSS[M] = loss(name, M)
    print(LOSS)
    if 0.99 > LOSS[M][0] or 47 > LOSS[M][1]:
      os.remove(subname(name, M))
      R = M-1
      
    else:
      os.remove(subname(name, M))
      L = M+1
  encode_hevc(name, R)
  
  if R>1 and os.path.exists(subname(name, 1)):
    os.remove(subname(name, 1))
  
  # stat_origin = os.stat(name)
  # stat_hevc = os.stat(subname(name, R))
  # if stat_origin.st_size < stat_hevc.st_size:
  #   shutil.move(subname(name, R), retname(name))

  print(LOSS)
  
if __name__=='__main__':
  if len(sys.argv) != 2:
    print("Usage: {} <target dir>".format(sys.argv[0]))
    exit(1)
  logging.basicConfig(level=logging.INFO)
  
  files = getFiles(sys.argv[1])
  for f in files:
    encode_search(f)
    