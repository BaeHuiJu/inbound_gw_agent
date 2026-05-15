# Teams 메시지는 Power Automate 브릿지를 통해 Outlook 받은편지함으로 전달됩니다.
# OutlookReader가 '[TEAMS]' 접두사 메일을 감지해 MessageSource.TEAMS 로 분류합니다.
#
# Power Automate 플로우 설정 방법:
#   1. https://make.powerautomate.com 접속
#   2. 새 플로우 → "자동화된 클라우드 흐름"
#   3. 트리거: "Teams 채널에 새 메시지 게시됨" 또는 "새 채팅 메시지 수신"
#   4. 작업 추가 → "이메일 보내기(V2)"
#      - 받는 사람: 본인 이메일
#      - 제목:  [TEAMS] @{triggerBody()?['channelIdentity']?['channelId']}: @{triggerBody()?['summary']}
#      - 본문:
#          보낸 사람: @{triggerBody()?['from']?['user']?['displayName']}
#          채널: @{triggerBody()?['channelIdentity']?['channelId']}
#          시각: @{triggerBody()?['createdDateTime']}
#          ---
#          @{triggerBody()?['body']?['content']}
