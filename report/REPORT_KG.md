# Báo cáo Day 19 — Flat RAG vs GraphRAG

**Họ tên:** Nguyễn Viết Hoàng Hải  **MSSV:** 2A202602967  **Ngày:** 05/10/2026

> Kỳ vọng và thang điểm: `SUBMISSION.md`. Mọi số liệu phải khớp với `ket_qua_benchmark_kg.txt`. Bản thiết kế ontology nộp riêng ở `report/ONTOLOGY.md`.

---

## 1. Chi phí (10 điểm)

Dán 2 bảng `Indexing` và `Querying` từ `ket_qua_benchmark_kg.txt`:

```
Chat model: openrouter:openai/gpt-4o-mini | Embedding: openrouter:openai/text-embedding-3-small | top_k=3 | chunk_size=800 | chunks=176 | KG: 204 nodes / 383 rels

== Indexing (one-off)
pipeline  calls    in_tok  out_tok       USD  seconds
flat        176     56072        0   0.00112    249.2
graph       196     91958     4832   0.00940    349.9

== Querying (mean per question)
pipeline  recall  judge   in_tok  out_tok       USD  seconds
flat        0.43   1.00      694       47   0.00013     2.60
graph       0.74   1.33     2885       86   0.00048     3.46
```

| Chỉ số | Flat | Graph | Graph / Flat |
| --- | --- | --- | --- |
| Indexing USD | 0.00112 | 0.00940 | ×8.39 |
| Indexing giây | 249.2 | 349.9 | ×1.40 |
| Mỗi câu: USD | 0.00013 | 0.00048 | ×3.69 |
| Mỗi câu: giây | 2.60 | 3.46 | ×1.33 |
| Mỗi câu: in_tok | 694 | 2885 | ×4.16 |

**Chi phí tăng thêm đến từ đâu?** (2–3 câu)
> Ở giai đoạn **Indexing**, chi phí USD tăng gấp **8.39 lần** chủ yếu do GraphRAG phải gọi thêm 20 lượt LLM để trích xuất cấu trúc thực thể và quan hệ (vụ án, đối tượng, chất, tội danh) từ toàn bộ các bài báo tin tức tự do (`in_tok` tăng từ 56k lên 92k và sinh 4.8k `out_tok`).
> Ở giai đoạn **Querying**, chi phí mỗi câu tăng gấp **3.69 lần** và `in_tok` tăng **4.16 lần** là do prompt của GraphRAG được chèn thêm danh sách các dữ kiện đồ thị multi-hop (tóm tắt vụ án, các khoản điều luật liên quan), làm ngữ cảnh đầu vào dài hơn đáng kể so với chỉ 3 chunk văn bản đơn thuần của Flat RAG.

---

## 2. Từng câu hỏi (10 điểm)

| Câu | Loại | Flat recall / judge | Graph recall / judge | Thắng | Vì sao (1 câu) |
| --- | --- | --- | --- | --- | --- |
| **Q1** | single-hop-law | 1.00 / 2 | 1.00 / 2 | Hòa | Câu hỏi định nghĩa tiền chất nằm gọn trong một đoạn văn bản của Luật PCMT 2021 nên cả hai pipeline đều tìm và trả lời chính xác. |
| **Q2** | single-hop-news | 1.00 / 2 | 1.00 / 2 | Hòa | Thông tin hai bị cáo nhận án tử hình nằm trọn vẹn trong một bài báo tin tức nên Flat RAG tìm đúng ngay qua vector search, đồ thị không cần can thiệp. |
| **Q3** | cross-kb | 0.00 / 0 | 1.00 / 2 | **Graph** | Flat RAG bị đứt thông tin do bài báo không nêu khung hình phạt Điều 251, trong khi GraphRAG đi qua node cầu nối `Crime` để lấy chính xác khoản 1 Điều 251 BLHS. |
| **Q4** | cross-kb | 0.00 / 0 | 0.00 / 0 | Hòa | Cả hai cùng thất bại vì Flat RAG thiếu liên kết luật, còn GraphRAG bị hạn chế bởi bộ lọc KG-3 chỉ lấy khoản 1 thay vì khung phạt tối đa (khoản 4) của Điều 255. |
| **Q5** | cross-kb-multi-hop | 0.60 / 1 | 0.80 / 1 | **Graph** | GraphRAG kết nối được đối tượng Cái Quang Huy, chất MDMA và truy xuất khung hình phạt theo khoản tương ứng của Điều luật trong BLHS tốt hơn. |
| **Q6** | aggregation | 0.00 / 1 | 0.67 / 1 | **Graph** | Nhờ node trung tâm `MDMA`, GraphRAG gom được toàn bộ các vụ án và các Điều luật liên quan trong khi Flat RAG chỉ tổng hợp được các đoạn văn vụn vặt. |

---

## 3. Phân tích lỗi (20 điểm)

### Lỗi E1: Cầu nối gãy (Broken Bridge)

- **Hiện tượng:** Một số vụ việc trong tin tức tồn tại trong đồ thị dưới dạng node `Case`, nhưng hoàn toàn cô lập, không có quan hệ `CHARGED_WITH` để đi tới node `Crime` sang KB Luật.
- **Bằng chứng:** Truy vấn Cypher kiểm tra các `Case` không có cạnh `CHARGED_WITH`:

```cypher
MATCH (k:Case) WHERE NOT (k)-[:CHARGED_WITH]->() 
RETURN k.name AS name, k.doc_id AS doc_id;
```

```
name: "Vụ tông cảnh sát giao thông ở An Giang"
doc_id: "news-100260926112415229"
```

- **Nguyên nhân:** 
  1. *Ngôn ngữ báo chí:* Bài báo gốc `news-100260926112415229` đưa tin về một tài xế xe tải dương tính với ma túy đã tông xe vào CSGT. Hành vi chính được khởi tố là "chống người thi hành công vụ", chứ đối tượng chưa bị khởi tố về một tội danh cụ thể thuộc Chương XX BLHS (Các tội phạm về ma túy).
  2. *Cơ chế `link_entity`:* LLM không tìm thấy tội danh khớp trong `DANH SÁCH TỘI DANH` nên trường `charges` bị rỗng. Kết quả là node `Case` này không được tạo quan hệ `CHARGED_WITH`, dẫn đến cầu nối sang Luật bị gãy hoàn toàn đối với vụ việc này.
- **Đề xuất sửa:**
  Bổ sung quan hệ bắc cầu dự phòng `(Case)-[:INVOLVES]->(Substance)<-[:MENTIONS]-(Clause)` trong trường hợp tội danh chưa được khởi tố, hoặc mở rộng danh sách tội danh liên quan (ví dụ: các hành vi điều khiển phương tiện khi sử dụng chất cấm) để không làm đứt đường dẫn tri thức.

---

### Lỗi E2: Thiếu ngữ cảnh luật do bộ lọc truy xuất (Missing Legal Context)

- **Hiện tượng:** Tại câu hỏi **Q4** (*"Giang hồ 'Hoàng Nato' bị bắt về hành vi gì, và hành vi đó có thể bị phạt tù tối đa bao nhiêu theo Bộ luật Hình sự?"*), dù đồ thị có đầy đủ thông tin về Dương Minh Tuấn ("Hoàng Nato"), Vụ án, Tội tổ chức sử dụng trái phép chất ma túy và Điều 255 BLHS, GraphRAG vẫn trả về `"Không đủ thông tin."` (judge = 0, recall = 0.00).
- **Bằng chứng:** 
  Kiểm tra các dữ kiện đồ thị được sinh ra bởi `graph.context(q4, [])`:

```cypher
MATCH (p:Person {name: 'Dương Minh Tuấn'})-[r:INVOLVED_IN]->(k:Case)-[:CHARGED_WITH]->(c:Crime)<-[:DEFINES]-(a:Article)-[:HAS_CLAUSE]->(cl:Clause)
RETURN a.id, cl.number, cl.penalty;
```

```
Dữ kiện thực tế được nạp vào Prompt:
- Vụ việc 'Vụ bắt giữ TikToker Phannhibeauty và giang hồ 'Hoàng Nato'': ... Hoàng Nato cũng bị bắt về hành vi tổ chức sử dụng trái phép chất ma túy.
- [Điều 255 BLHS - Tội tổ chức sử dụng trái phép chất ma túy] khoản 1: 1. Người nào tổ chức sử dụng trái phép chất ma túy dưới bất kỳ hình thức nào, thì bị phạt tù từ 02 năm đến 07 năm.
```

- **Nguyên nhân:**
  Trong hàm `Neo4jGraph.context` (KG-3), quy tắc lọc khoản luật hiện tại là:
  `WHERE cl.number = 1 OR EXISTS { MATCH (k)-[:INVOLVES]->(:Substance)<-[:MENTIONS]-(cl) }`.
  1. Quy tắc này **chỉ lấy khoản 1** (khung cơ bản: phạt tù từ 02 năm đến 07 năm).
  2. Các khoản tăng nặng (khoản 2, 3, 4) chỉ được lấy nếu khoản đó `MENTIONS` một chất mà vụ án đó `INVOLVES`. Tuy nhiên, Điều 255 BLHS phân định khung hình phạt tăng nặng theo *tình tiết phạm tội* (đối với 2 người trở lên, gây tổn hại sức khỏe, tái phạm nguy hiểm...) chứ các khoản 2, 3, 4 không liệt kê tên chất cụ thể!
  3. Hơn nữa, chất ma túy trong vụ của Hoàng Nato là `etomidate` (không nằm trong danh mục các chất phổ biến của BLHS).
  Hậu quả là khoản 4 Điều 255 (khung phạt cao nhất: *20 năm tù hoặc tù chung thân*) bị lọc bỏ, không được đưa vào prompt. LLM được chỉ thị *"Nếu ngữ cảnh không đủ, nói không đủ thông tin"* nên từ chối trả lời thay vì tự ý bịa đặt.
- **Đề xuất sửa:**
  Khi câu hỏi chứa các từ khóa hỏi về mức án tối đa (`tối đa`, `khung cao nhất`, `nặng nhất`, `kịch khung`), `context()` cần nhận diện intent này và bổ sung thêm khoản có `number = max(cl.number)` của Điều luật đó vào prompt.
  *Đánh đổi:* Phải thêm regex phát hiện ý định hỏi mức phạt tối đa hoặc tăng số lượng khoản nạp vào prompt (+50 đến +150 input tokens cho mỗi câu hỏi liên quan đến điều luật).

---

## 4. Kết luận (5 điểm)

Khi nào nên dùng KG, khi nào Flat RAG là đủ? Dẫn số liệu ở mục 1–2:

1. **Khi nào Flat RAG là đủ:**
   - Khi câu hỏi thuộc dạng **Single-hop (đơn nguồn)**, nơi câu trả lời nằm gọn trong một đoạn văn bản cục bộ (như câu **Q1** và **Q2**). Cả Flat RAG và GraphRAG đều đạt `recall = 1.00` và `judge = 2.00`.
   - Trong kịch bản này, Flat RAG tối ưu hơn vượt bậc về kinh tế và độ trễ: chi phí indexing rẻ hơn **8.39 lần** ($0.00112 vs $0.00940), chi phí mỗi lượt hỏi rẻ hơn **3.69 lần** ($0.00013 vs $0.00048), và tốc độ phản hồi nhanh hơn 33% (2.60s vs 3.46s). Do đó, với tài liệu đồng nhất và câu hỏi tra cứu thông thường, không nên tốn chi phí xây dựng Knowledge Graph.

2. **Khi nào nên dùng GraphRAG:**
   - Khi hệ thống phải đối mặt với bài toán **Cross-KB (liên cơ sở tri thức)** hoặc **Multi-hop / Aggregation**, nơi thông tin bị phân mảnh ở nhiều nguồn độc lập (Ví dụ: tên bị cáo và hành vi ở KB Tin tức, còn định danh Điều luật và khung hình phạt ở KB Luật).
   - Minh chứng từ số liệu đo lường: Tại câu **Q3**, Flat RAG hoàn toàn bất lực (`recall = 0.00, judge = 0`), trong khi GraphRAG đạt điểm tuyệt đối (`recall = 1.00, judge = 2`). Tính trung bình toàn bộ benchmark, GraphRAG nâng `recall` từ **0.43 lên 0.74** (+72%) và điểm `judge` từ **1.00 lên 1.33**.
   - **Điểm hòa vốn:** Dù chi phí thiết lập ban đầu cao hơn $0.00828, nhưng với các hệ thống tra cứu nghiệp vụ (pháp lý, y tế, điều tra) nơi tính chính xác và khả năng tổng hợp liên tài liệu là bắt buộc, khoản đầu tư cho Knowledge Graph là hoàn toàn xứng đáng.

---

## 5. Tự kiểm (5 điểm)

```
$ pytest tests/ -q
................................................                         [100%]
48 passed in 0.08s

$ python bench_kg.py --check
[OK] Dữ liệu: 18 điều luật, 20 bài báo
[OK] KG-1 link_entity
[OK] Neo4j kết nối được
[provider] chat = openrouter:openai/gpt-4o-mini | embedding = openrouter:openai/text-embedding-3-small
[OK] KG-2 build_graph: 146 node / 289 cạnh, đường xuyên 2 KB dài 2 cạnh
[OK] KG-3 context: 13 dữ kiện, có Điều 251
[OK] KG-4 GraphRAGAgent.answer
[OK] Chi phí check: 1 lần gọi LLM, $0.00064. Graph nhỏ (luật + 1 bài) vẫn còn trong Neo4j để bạn xem; chạy --judge để dựng graph đầy đủ.
```

Ảnh Neo4j: `report/img/kg_count.png`, `report/img/kg_cross_kb.png`, `report/img/kg_my_case.png`.
Người đã chọn cho `kg_my_case.png`: **Trần Thanh Tuấn** (Bị cáo trong vụ đường dây mua bán hơn 36kg ma túy tại TP.HCM, kết nối xuyên sang Điều 251 và Điều 255 BLHS).

---

## Vấn đề gặp phải (không tính điểm)

- **Môi trường Windows và Docker Service:** Trên môi trường máy Windows, dịch vụ Docker Desktop service bị tắt ban đầu và cần quyền admin để start service Windows; giải pháp khắc phục triệt để và tự động hóa là kích hoạt Docker daemon và container Neo4j chính thức bên trong hệ thống Linux WSL2, cấu hình port mapping (`7474`, `7687`) tương thích 100% với môi trường Python trên Windows.
- **PowerShell UTF-8 BOM encoding:** PowerShell khi tạo file text mặc định thêm ký tự BOM (`\ufeff`) ở đầu file khiến `load_dotenv` không parse được tên biến môi trường đầu tiên; đã khắc phục bằng cách chuyển định dạng UTF-8 không BOM chuẩn.
