from aws_cdk import (
    aws_ec2 as ec2,
    aws_elasticloadbalancingv2 as elbv2,
    aws_iam as iam,
    Stack,
    core
)

from constructs import Construct

class CdkHwWebServerAlbStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Parameters
        instance_type_input = core.CfnParameter(self, "InstanceType", type="String", description="EC2 instance type")
        key_pair = core.CfnParameter(self, "KeyPair", type="String", description="EC2 Key Pair")
        your_ip = core.CfnParameter(self, "YourIp", type="String", description="Your IP address")

        # VPC and Subnets
        vpc = ec2.Vpc(self, "EngineeringVpc",
                      cidr="10.0.0.0/18",
                      max_azs=2,
                      subnet_configuration=[
                          ec2.SubnetConfiguration(name="PublicSubnet1", cidr_mask=24, subnet_type=ec2.SubnetType.PUBLIC),
                          ec2.SubnetConfiguration(name="PublicSubnet2", cidr_mask=24, subnet_type=ec2.SubnetType.PUBLIC)
                      ])

        # Security Group
        sg = ec2.SecurityGroup(self, "WebserversSG",
                               vpc=vpc,
                               description="Allow SSH and HTTP access",
                               allow_all_outbound=True)
        sg.add_ingress_rule(ec2.Peer.ipv4(your_ip.value_as_string + "/32"), ec2.Port.tcp(22), "SSH Access")
        sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(80), "HTTP Access")

        # EC2 Instances
        ami_linux = ec2.MachineImage.generic_linux({"us-east-2": "ami-01cc34ab2709337aa"})
        
        for i, subnet in enumerate(["PublicSubnet1", "PublicSubnet2"], start=1):
            ec2.Instance(self, f"web{i}",
                         instance_type=ec2.InstanceType(instance_type_input.value_as_string),
                         machine_image=ami_linux,
                         vpc=vpc,
                         vpc_subnets=ec2.SubnetSelection(subnet_group_name=subnet),
                         key_name=key_pair.value_as_string,
                         security_group=sg,
                         user_data=ec2.UserData.custom("""
                                #!/bin/bash
                                yum update -y
                                yum install -y git httpd php
                                service httpd start
                                chkconfig httpd on
                                aws s3 cp s3://seis665-public/index.php /var/www/html/""")
                        )

        # Load Balancer
        lb = elbv2.ApplicationLoadBalancer(self, "EngineeringLB",
                                           vpc=vpc,
                                           internet_facing=True)
                                           
        listener = lb.add_listener("Listener", port=80)
        target_group = listener.add_targets("EngineeringWebservers",
                                            port=80,
                                            targets=[elbv2.InstanceTarget(instance_id=f"web{i}", port=80) for i in range(1, 3)])

        # Health Check
        target_group.configure_health_check(path="/", port="80", protocol=elbv2.Protocol.HTTP)
        
