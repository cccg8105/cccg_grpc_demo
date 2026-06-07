.PHONY: proto data up down logs demo smoke smoke-rest presentation

proto:
	.venv/Scripts/python scripts/generate_proto.py

data:
	.venv/Scripts/python scripts/generate_sample_csv.py --rows 50000

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

demo: proto data up

smoke:
	.venv/Scripts/python scripts/smoke_test.py

smoke-rest:
	.venv/Scripts/python scripts/smoke_test_rest.py

presentation:
	quarto render presentation/grpc-intro.qmd
	.venv/Scripts/python scripts/patch_presentation_html.py

presentation-verify:
	.venv/Scripts/python scripts/capture_presentation_slides.py
