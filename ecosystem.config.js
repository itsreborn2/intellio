module.exports = {
  apps: [
    {
      name: 'turbo-app-dev',
      script: 'npx',
      //args: 'turbo run dev --filter=main --filter=stockeasy',
      args: 'turbo run dev',
      watch: false,
      autorestart: true,
      env: {
        NODE_ENV: 'development'
      }
    },
  {
    name: 'turbo-app',
    script: 'npx',
    //args: 'turbo run start --filter=main --filter=stockeasy',
    args: 'turbo run serve',
    watch: false,
    autorestart: true,
    instances: 2,
    exec_mode: 'cluster',
    env: {
      NODE_ENV: 'production'
    }
  }
]
}
