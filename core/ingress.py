"""
Run nginx as an ingress conroller.
"""

def gen_location(c):
    return "location {0} {{ proxy_pass http://{1}; }}".format(c["path"], c["endpoint"])

def create_conf(path, port, conf):
    with open(path, "w") as cf:
        cf.write("events{}\n")

        cf.write("http {\n")
        cf.write("  server {\n")
        cf.write("    listen {0};\n".format(port))

        for c in conf:
            cf.write("    " + gen_location(c) + "\n")

        cf.write("  }\n")
        cf.write("}\n")

def ingress_command(path):
    return "nginx -c {0}".format(path)
