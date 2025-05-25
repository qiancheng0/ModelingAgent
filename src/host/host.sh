export CUDA_VISIBLE_DEVICES=4,6

#vllm serve /shared/nas2/shared/llms/Qwen2.5-72B-Instruct \
#    --max-model-len 32768 \
#    --gpu-memory-utilization 0.9 \
#    --tensor-parallel-size 8 \
#    --enable-auto-tool-choice \
#    --tool-call-parser hermes \
#    --chat-template tool_chat_hermes_template.jinja

# vllm serve /shared/nas2/shared/llms/Llama-3.1-70B-Instruct \
#     --max-model-len 32768 \
#     --gpu-memory-utilization 0.9 \
#     --tensor-parallel-size 8 \
#     --enable-auto-tool-choice \
#     --tool-call-parser llama3_json \
#     --chat-template tool_chat_llama3.1_template.jinja

vllm serve /shared/nas2/shared/llms/QwQ-32B \
    --gpu-memory-utilization 0.9 \
    --tensor-parallel-size 2 \
    --enable-auto-tool-choice \
    --tool-call-parser hermes \
    --chat-template tool_chat_hermes_template.jinja

