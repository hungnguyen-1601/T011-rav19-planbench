from setuptools import find_packages, setup

package_name = "planbench_simulator_node"

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
    description="ROS 2 node exposing the PlanBench simulator to Nav2.",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "simulator_node = planbench_simulator_node.simulator_node:main",
        ],
    },
)
