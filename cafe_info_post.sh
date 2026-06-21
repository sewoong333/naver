#!/bin/bash
# 네이버 카페 정보글 일일 포스팅 - 악기/음악 관련 SEO 정보글
cd /Users/se-ung/.hermes/profiles/choi-yonghyun/scripts/cafe-crawler
/Users/se-ung/.hermes/hermes-agent/venv/bin/python3 -u publish_info_article.py 2>&1
echo "Exit code: $?"
