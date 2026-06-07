import { ModelGatewayConsole } from "@/components/model-gateway/model-gateway-console";
import { getModelGatewayStatus } from "@/lib/api/sagad-api";

export default async function ModelGatewayPage() {
  const status = await getModelGatewayStatus();

  return <ModelGatewayConsole status={status} />;
}
