.PHONY: data test eval demo app all
data:
	python -m datagen.generate
test:
	python -m pytest -q
eval:
	python -m eval.run_eval
demo:
	python demo.py
app:
	streamlit run app/approval_app.py
all: data test eval
