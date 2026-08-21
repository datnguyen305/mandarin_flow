FROM golang:1.26-alpine AS build

WORKDIR /src
COPY go.mod ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/mandarin-flow-api ./cmd/api

FROM alpine:3.22
RUN apk add --no-cache ca-certificates
COPY --from=build /out/mandarin-flow-api /usr/local/bin/mandarin-flow-api
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/mandarin-flow-api"]
