PROJECT := pokemon-qa
ROOT := $(shell pwd)

.PHONY: kind-up kind-down build-images load-images deploy undeploy restart

kind-up:
	kind create cluster --config infra/kind/kind-config.yaml
	kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml

kind-down:
	kind delete cluster --name pokemon-qa

build-images:
	docker build -t pokemon-qa-backend:dev backend
	docker build -t pokemon-qa-worker:dev -f backend/worker.Dockerfile backend
	docker build -t pokemon-qa-frontend:dev frontend

load-images:
	kind load docker-image pokemon-qa-backend:dev --name pokemon-qa
	kind load docker-image pokemon-qa-worker:dev --name pokemon-qa
	kind load docker-image pokemon-qa-frontend:dev --name pokemon-qa

deploy:
	kubectl apply -k infra/k8s/base

undeploy:
	kubectl delete -k infra/k8s/base

restart:
	kubectl rollout restart deployment -n $(PROJECT)
