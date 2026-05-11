# Roxy GPT-SoVITS 本地 TTS 服务

这是一个给当前 Mac 本机部署的独立 TTS 服务层，使用：

- GPT-SoVITS 官方推理代码
- 洛琪希 `RoxyPro（新版）` 权重
- 本地参考音频默认声线
- HTTP 接口，后续可以直接接你们产品

## 目录

- 部署根目录：`/Users/umikok7/Desktop/python/my-deer-flow/artifacts/gpt-sovits-roxy`
- 服务脚本：`/Users/umikok7/Desktop/python/my-deer-flow/scripts/tts/roxy_gsv_service.py`
- 启动脚本：`/Users/umikok7/Desktop/python/my-deer-flow/scripts/tts/run_roxy_gsv_service.sh`
- 默认输出目录：`/Users/umikok7/Desktop/python/my-deer-flow/artifacts/gpt-sovits-roxy/outputs`

## 当前默认模型

- GPT 权重：`/Users/umikok7/Downloads/洛琪希GSV模型260426/RoxyPro（新版）/Roxy_Pro.ckpt`
- SoVITS 权重：`/Users/umikok7/Downloads/洛琪希GSV模型260426/RoxyPro（新版）/Roxy_Pro.pth`
- 默认参考音频：`/Users/umikok7/Downloads/洛琪希GSV模型260426/RoxyPro（新版）/slicer_opt/おはようございます、ルディ。その….wav`
- 默认参考语种：`ja`
- 默认输出语种：`zh`

## 启动

```bash
/Users/umikok7/Desktop/python/my-deer-flow/scripts/tts/run_roxy_gsv_service.sh
```

默认监听：

```text
http://127.0.0.1:9881
```

## 健康检查

```bash
curl http://127.0.0.1:9881/health
```

## 直接返回音频

```bash
curl -X POST http://127.0.0.1:9881/tts \
  -H 'Content-Type: application/json' \
  -o /tmp/roxy-test.wav \
  -d '{
    "text": "本次任务已经顺利完成，交付结果已整理完毕，请您查收。",
    "text_lang": "zh"
  }'
```

## 保存到文件并返回路径

```bash
curl -X POST http://127.0.0.1:9881/tts/file \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "本次任务已经顺利完成，交付结果已整理完毕，请您查收。",
    "text_lang": "zh"
  }'
```

## 常用可选参数

请求体支持这些字段：

- `text`
- `text_lang`
- `ref_audio_path`
- `prompt_text`
- `prompt_lang`
- `speed_factor`
- `top_k`
- `top_p`
- `temperature`

如果不传 `prompt_text`，服务会自动用参考音频文件名作为默认 prompt 文本。

## 环境变量

可选覆盖项：

- `ROXY_GSV_T2S_WEIGHTS`
- `ROXY_GSV_VITS_WEIGHTS`
- `ROXY_GSV_REF_AUDIO`
- `ROXY_GSV_PROMPT_LANG`
- `ROXY_GSV_TEXT_LANG`
- `ROXY_GSV_HOST`
- `ROXY_GSV_PORT`
