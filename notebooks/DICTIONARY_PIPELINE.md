# CVDICT OpenAI normalization pipeline

Pipeline này giữ CVDICT làm nguồn gốc, dùng OpenAI Batch API để chuẩn hóa dữ liệu và chỉ import bản đã validate.

## Cài dependency

```bash
pip install -r notebooks/requirements.txt
export OPENAI_API_KEY="..."
```

## Chạy thử

```bash
python -u notebooks/normalize_cvdict_openai.py prepare --limit 200 --batch-size 50
python -u notebooks/normalize_cvdict_openai.py submit
python -u notebooks/normalize_cvdict_openai.py status
python -u notebooks/normalize_cvdict_openai.py download
```

`submit` không cần giữ terminal mở. Có thể dùng `resume` ở phiên sau để kiểm tra và tự tải khi batch hoàn tất.

Kiểm tra các file `completed.jsonl`, `review.jsonl`, `errors.jsonl` và raw response trong
`data/openai_dictionary_normalization/` trước khi import.

## Chạy toàn bộ CVDICT

```bash
python -u notebooks/normalize_cvdict_openai.py prepare --batch-size 75
python -u notebooks/normalize_cvdict_openai.py submit
```

Entry đã hoàn thành với cùng `source_hash` được bỏ qua. Review queue cũng được bỏ qua trừ khi prepare với
`--include-review`. Lỗi API có thể retry bằng cách chạy lại `prepare` rồi `submit`.

## Export và import

```bash
python -u notebooks/normalize_cvdict_openai.py export
DATABASE_URL='postgresql://...' python -u notebooks/normalize_cvdict_openai.py import --confirm-reviewed
```

Chạy `alembic upgrade head` trước khi import. Lệnh import ưu tiên các entry `validated` và `reference`
trong `completed.jsonl`. Mọi source entry chưa hoàn thành được nhập với trạng thái `source_only`, giữ
pinyin và nghĩa CVDICT nhưng không tự tạo POS, định nghĩa hoặc ví dụ. Bản `source_only` không bao giờ ghi
đè một bản `validated`.

Go API tra từ theo thứ tự `validated` -> `source_only`. Nếu cả hai đều không có nghĩa, endpoint trả
`Chưa có nghĩa tiếng Việt.` và không chuyển tiếp yêu cầu sang Python hoặc OpenAI. Cờ
`--confirm-reviewed` vẫn bắt buộc để tránh ghi database ngoài ý muốn.

## Thêm thủ công một entry đã kiểm tra

Không sửa riêng `completed.jsonl`, vì importer yêu cầu entry tương ứng trong `source_entries.jsonl` và
`source_hash` phải khớp. Lệnh sau cập nhật đồng thời hai file và upsert PostgreSQL Docker:

```bash
python notebooks/normalize_cvdict_openai.py manual-upsert \
  --traditional 沒有人 \
  --simplified 没有人 \
  --pinyin-number "mei2 you3 ren2" \
  --meaning "không có ai" \
  --part-of-speech phrase \
  --sync-compose
```

ID ổn định và `ON CONFLICT` giúp chạy lại lệnh mà không tạo entry trùng.
