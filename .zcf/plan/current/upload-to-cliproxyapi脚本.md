# upload-to-cliproxyapi.sh 脚本开发计划

## 任务
编写独立 Shell 脚本，支持交互式选择 1~4 份分割方式，将本地授权文件均分上传到阿里云服务器对应 CLIProxyAPI 目录，并重启服务。

## 步骤
1. 创建 scripts/upload-to-cliproxyapi.sh
2. 实现预检查、交互选择、备份、清空、分组上传、重启服务、验证全流程
3. 支持 -n 和 -s 参数

## 状态
- 执行中
