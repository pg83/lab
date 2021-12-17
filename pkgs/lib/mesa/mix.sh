{% extends '//mix/template/meson.sh' %}

{% block fetch %}
https://archive.mesa3d.org//mesa-21.3.1.tar.xz
d6efe1ecc0680cd1adb942f05600d884
{% endblock %}

{% block lib_deps %}
lib/c/mix.sh
lib/z/mix.sh
lib/drm/mix.sh
lib/zstd/mix.sh
#lib/llvm/mix.sh
lib/expat/mix.sh
lib/wayland/mix.sh
lib/elfutils/mix.sh
lib/vulkan/loader/mix.sh
lib/vulkan/headers/mix.sh
{% endblock %}

{% block bld_libs %}
pypi/Mako/mix.sh
{% endblock %}

{% block bld_tool %}
dev/lang/flex/mix.sh
dev/lang/bison/3/8/mix.sh
dev/build/make/mix.sh
lib/wayland/protocols/mix.sh
{% endblock %}

{% block meson_flags %}
-Ddri-drivers=
-Dvulkan-drivers=amd
-Dgallium-drivers=zink

-Dvalgrind=disabled
-Dlibunwind=disabled

-Dplatforms=wayland
-Degl-native-platform=wayland

-Degl=enabled
-Dglx=disabled
-Dgles2=enabled
-Dopengl=true
-Dgallium-nine=false

{% if kind == 'bin' %}
-Dtools=glsl
{% endif %}

-Dcpp_rtti=false
-Dshader-cache=disabled
-Dllvm=disabled
-Dshared-llvm=disabled
{% endblock %}

{% block step_setup %}
export CPPFLAGS="-Dhandle_table_remove=mesa_handle_table_remove -Dos_create_anonymous_file=os_create_anonymous_file_mesa ${CPPFLAGS}"
{{super()}}

export PC_H=$(
    export PKG_COFIG_PATH=
    source_env "${MIX_B_DIR}:${MIX_H_DIR}"
    echo ${PKG_CONFIG_PATH}
)

export PC_T=$(
    export PKG_COFIG_PATH=
    source_env "${MIX_T_DIR}"
    echo ${PKG_CONFIG_PATH}
)

echo "h ${PC_H}"
echo "t ${PC_T}"
{% endblock %}

{% block patch %}
#cat meson.build | grep -v 'DUSE_ELF_TLS' > _ && mv _ meson.build

pushd src/gallium/frontends/dri

for l in *.c *.h; do
    for x in dri2_lookup_egl_image dri2_validate_egl_image; do
        sed -e "s|${x}|${x}_xxx|g" -i ${l}
    done
done

popd; pushd src/gallium/drivers/radeonsi

for l in *.c *.h *.cpp; do
    for x in vi_alpha_is_on_msb si_emit_cache_flush si_cp_dma_prefetch si_cp_dma_clear_buffer si_cp_dma_wait_for_idle; do
        sed -e "s|${x}|${x}_xxx|g" -i ${l}
    done
done
{% endblock %}

{% block install %}
{{super()}}

cd ${out}/lib

mv dri/zink_dri.so libdrivers.a
rm -rf dri

mkdir tmp && cd tmp

cat << EOF > ${tmp}/fix.py
import os
import sys

def rn(fr, to):
    if fr != to:
        print(f'rename {fr} {to}')
        os.rename(fr, to)

n = sys.argv[1].replace('/', '_').replace('.', '_')

for x in list(os.listdir('.')):
    print(f'got {x}')
    rn(x, x[:-2].replace('.', '_') + x[-2:])

for x in list(os.listdir('.')):
    if x.startswith('___'):
        rn(x, 'Z' + n + x)
EOF

for l in ../*.a; do
    llvm-ar x ${l}
    python3 ${tmp}/fix.py ${l}
done

rm si_state_draw* && for i in 1 2 3 4 5 6; do
    llvm-ar -xN ${i} ../libdrivers.a si_state_draw.cpp.o
    mv si_state_draw.cpp.o si_state_draw_cpp_${i}.o
done

rm *libGLESv1*entry*
rm meson*vulkan_util*
rm *egl_wayland_wayland-drm_linux-dmabuf-unstable-v1-protocol*
rm *libvulkan_radeon_a___spirv_*

${AR} q libfullgl.a *.o

echo > empty.c

${CC} -c empty.c
${AR} q libempty.a empty.o

cd ..

mkdir big
mv tmp/libempty.a tmp/libfullgl.a big/
rm -rf tmp

for l in *.a; do
    rm ${l} && ln -s big/libempty.a ${l}
done

ln -s big/libfullgl.a .
{% endblock %}

{% block env %}
export COFLAGS="--with-gallium=${out} \${COFLAGS}"
{% endblock %}
