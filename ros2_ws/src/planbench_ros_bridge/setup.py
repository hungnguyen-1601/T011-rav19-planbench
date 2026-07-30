from setuptools import find_packages, setup

package_name = "planbench_ros_bridge"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="PlanBench",
    maintainer_email="mebayluon@gmail.com",
    description="Pure conversions between PlanBench domain objects and ROS 2 messages.",
    license="Apache-2.0",
)
