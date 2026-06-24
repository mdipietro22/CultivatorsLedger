import { prisma } from './src/lib/prisma'

async function main() {
  const count = await prisma.climateLog.count()
  console.log(`✅ Climate logs: ${count}`)
}
main().catch(console.error)
